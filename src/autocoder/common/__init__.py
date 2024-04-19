import pydantic
import ast
import sys
import subprocess
import os
import time
from typing import List,Dict,Any,Optional

class SourceCode(pydantic.BaseModel):
    module_name: str
    source_code: str
    tag: str = ""


class TranslateReadme(pydantic.BaseModel):
    filename:str = pydantic.Field(...,description="需要翻译的文件路径")
    content:str  = pydantic.Field(...,description="翻译后的内容")


class Translates(pydantic.BaseModel):
    readmes:List[TranslateReadme]

class TranslateArgs(pydantic.BaseModel):
    '''
    示例：把项目中的markdown文档翻译成中文
    此时对应的字段值应该是
    target_lang=中文
    file_suffix=.md
    new_file_mark=cn
    '''
    target_lang: str = pydantic.Field(..., description="The target language to translate to")
    file_suffix: str = pydantic.Field(..., description="to filter the file by suffix, e.g. py, ts, md, etc. if multiple, use comma to separate")    
    new_file_mark: str = pydantic.Field(..., description="according to the file suffix, the new file name should be like this: filename-new_file_mark.file_suffix")    

class ExecuteStep(pydantic.BaseModel):
    code: str = pydantic.Field(..., description="The code line to execute, e.g. `print('hello world')` or `ls -l`, shell or python code.")
    lang: str = pydantic.Field(..., description="The language to execute the code line, python,shell. default is python")
    total_steps: Optional[int] = pydantic.Field(-1, description="The total steps to finish the user's question")
    current_step: Optional[int] = pydantic.Field(-1, description="The current step to finish the user's question")
    cwd: Optional[str] = pydantic.Field(None, description="The current working directory to execute the command line")
    env: Optional[Dict[str, Any]] = pydantic.Field(None, description="The environment variables to execute the command line")
    timeout: Optional[int] = pydantic.Field(None, description="The timeout to execute the command line")
    ignore_error: Optional[bool] = pydantic.Field(False, description="Ignore the error of the command line")

class ExecuteSteps(pydantic.BaseModel):
    steps:List[ExecuteStep]


class EnvInfo(pydantic.BaseModel):
    os_name: str
    os_version: str
    python_version: str
    conda_env: Optional[str]
    virtualenv: Optional[str] 
    has_bash: bool

class AutoCoderArgs(pydantic.BaseModel):
    source_dir: Optional[str] = pydantic.Field(..., description="Path to the project")
    git_url: Optional[str] = pydantic.Field(None, description="URL of the git repository")
    target_file: Optional[str] = pydantic.Field(None, description="the file to write the source code to")
    query: Optional[str] = pydantic.Field(None, description="the instruction to handle the source code")
    template: str = pydantic.Field("common", description="the instruction to handle the source code")
    project_type: str = pydantic.Field("py", description="the type of the project. py, ts, py-script, translate, or file suffix. default is py")
    execute: bool = pydantic.Field(False, description="Execute command line or not")
    enable_multi_round_generate:bool = False
    package_name: str = pydantic.Field("", description="only works for py-script project type. The package name of the script. default is empty.")
    script_path: str = pydantic.Field("", description="only works for py-script project type. The path to the Python script. default is empty.")
    image_file: str = ""
    ray_address: str = ""
    
    
    model: str = pydantic.Field("", description="the model name to use")
    model_max_length: int = pydantic.Field(1024, description="the maximum length generated by the model. default is 1024 this only works when model is specified.")
    model_max_input_length: int = pydantic.Field(6000, description="The maximum input length of the model") 
    
    file: Optional[str] = pydantic.Field(None, description="the configuration file to use")
    anti_quota_limit: Optional[int] = pydantic.Field(1, description="After how much time to wait for the next request. default is 1s")
    skip_build_index: bool = pydantic.Field(True, description="Skip building index or not. default is True")
    print_request: bool = pydantic.Field(False, description="Print request to model or not. default is False")
    human_as_model: bool = pydantic.Field(False, description="Use human as model or not. default is False")
    py_packages: str = pydantic.Field("", description="The Python packages added to context,only works for py project type. default is empty.")
    
    urls: str = pydantic.Field("", description="The urls to crawl and extract text from, separated by comma")
    urls_use_model:bool = True

    search_engine: str = ""
    search_engine_token: str = ""
    enable_rag_search:bool
    enable_rag_context:bool
    required_exts:str = ""
    
    auto_merge: bool = pydantic.Field(False, description="Whether to automatically merge the generated code into the existing file")
    vl_model: str = ""
    sd_model: str = ""
    emb_model: str = ""
    
    index_model: str = ""
    index_model_max_length: int = pydantic.Field(0, description="the maximum length generated by the model. default is 0 this only works when model is specified.")
    index_model_max_input_length: int = pydantic.Field(0, description="The maximum input length of the model") 
    index_model_anti_quota_limit: Optional[int] = pydantic.Field(0, description="After how much time to wait for the next request. default is 0s")
    index_filter_level: int = 3
    index_filter_workers: int = 1
    image_max_iter: int = 1 

    class Config:
        protected_namespaces = ()


def is_likely_useful_file(file_path):
    """Determine if the file is likely to be useful by excluding certain directories and specific file types."""
    excluded_dirs = ["docs", "examples", "tests", "test", "__pycache__", "scripts", "benchmarks","build"]
    utility_or_config_files = ["hubconf.py", "setup.py"]
    github_workflow_or_docs = ["stale.py", "gen-card-", "write_model_card"]
    
    if any(part.startswith('.') for part in file_path.split('/')):
        return False
    if 'test' in file_path.lower():
        return False
    for excluded_dir in excluded_dirs:
        if f"/{excluded_dir}/" in file_path or file_path.startswith(excluded_dir + "/"):
            return False
    for file_name in utility_or_config_files:
        if file_name in file_path:
            return False
    for doc_file in github_workflow_or_docs:
        if doc_file in file_path:
            return False
    return True

def is_test_file(file_content):
    """Determine if the file content suggests it is a test file."""
    test_indicators = ["import unittest", "import pytest", "from unittest", "from pytest"]
    return any(indicator in file_content for indicator in test_indicators)

def has_sufficient_content(file_content, min_line_count=10):
    """Check if the file has a minimum number of substantive lines."""
    lines = [line for line in file_content.split('\n') if line.strip() and not line.strip().startswith('#')]
    return len(lines) >= min_line_count

def remove_comments_and_docstrings(source):
    """Remove comments and docstrings from the Python source code."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)) and ast.get_docstring(node):
            node.body = node.body[1:]  # Remove docstring
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Str):
            node.value.s = ""  # Remove comments
    return ast.unparse(tree)

def split_code_into_segments(source_code, max_tokens=1024):
    """Split the source code into segments of length up to max_tokens."""
    segments = []
    while len(source_code) > max_tokens:
        split_point = source_code.rfind('\n', 0, max_tokens)
        if split_point == -1:  # If no newline is found,
            split_point = max_tokens  # split at max_tokens
        segments.append(source_code[:split_point])
        source_code = source_code[split_point:]
    segments.append(source_code)
    return segments


def detect_env() -> EnvInfo:
        os_name = sys.platform
        os_version = ""
        if os_name == "win32":
            os_version = sys.getwindowsversion().major
        elif os_name == "darwin":
            os_version = subprocess.check_output(["sw_vers", "-productVersion"]).decode('utf-8').strip()
        elif os_name == "linux":
            os_version = subprocess.check_output(["uname", "-r"]).decode('utf-8').strip()
         
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        
        conda_env = os.environ.get("CONDA_DEFAULT_ENV")
        
        virtualenv = os.environ.get("VIRTUAL_ENV")
        
        has_bash = True
        try:
            subprocess.check_output(["bash", "--version"])
        except:
            has_bash = False
            
        return EnvInfo(
            os_name=os_name,
            os_version=os_version,
            python_version=python_version,
            conda_env=conda_env,
            virtualenv=virtualenv,
            has_bash=has_bash
        )


def chat_with_llm_step_by_step(llm,conversations, 
                               response_class, 
                               max_steps=30, 
                               anti_quota_limit=1):
    if max_steps == -1:
        max_steps = 30

    result = []
    t = llm.chat_oai(conversations=conversations, response_class=response_class,enable_default_sys_message=True)
    total_steps = max_steps
    current_step = 0

    while current_step < total_steps and t[0].value:        
        result.append(t[0].value)
        conversations.append({
            "role": "assistant",
            "content": t[0].response.output
        })
        print(f"{conversations[-1]['role']}: {conversations[-1]['content']}\n", flush=True)

        conversations.append({
            "role": "user",
            "content": "继续"
        })
        print(f"{conversations[-1]['role']}: {conversations[-1]['content']}\n", flush=True)        
        t = llm.chat_oai(conversations=conversations, response_class=response_class,enable_default_sys_message=True)        
        current_step += 1
        time.sleep(anti_quota_limit)

    return result, conversations

