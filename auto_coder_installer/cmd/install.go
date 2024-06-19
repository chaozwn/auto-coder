package cmd

import (
	"fmt"
	"os"
	"os/exec"
	"runtime"

	"github.com/spf13/cobra"
)

func checkCondaExists() bool {
	_, err := exec.LookPath("conda")
	return err == nil
}

func init() {
	rootCmd.AddCommand(installCmd)
}

var installCmd = &cobra.Command{
	Use:   "install",
	Short: "Install Auto-Coder",
	Long:  `Download and install Miniconda, create the auto-coder environment, and install the auto-coder package.`,
	Run: func(cmd *cobra.Command, args []string) {
		var downloadStatus, installStatus, envStatus, packageStatus, rayStatus, storageStatus bool

		if !checkCondaExists() {
			fmt.Println("Downloading Miniconda...")
			downloadStatus = downloadMiniconda()

			if downloadStatus {
				fmt.Println("Installing Miniconda...")
				installStatus = installMiniconda()
			} else {
				fmt.Println("Miniconda download failed. Aborting installation.")
				return
			}
		} else {
			fmt.Println("Conda is already installed. Skipping Miniconda download and install.")
			downloadStatus, installStatus = true, true
		}

		if installStatus {
			fmt.Println("Creating auto-coder environment...")
			envStatus = createEnvironment()
		}

		if envStatus {
			fmt.Println("Installing auto-coder package...")
			packageStatus = installAutoCoder()
		}

		if packageStatus {
			fmt.Println("Starting Ray cluster...")
			rayStatus = startRayCluster()

			if rayStatus {
				fmt.Println("Installing BytzerLLM storage...")
				storageStatus = installStorage()
			}
		}

		if downloadStatus && installStatus && envStatus && packageStatus && rayStatus && storageStatus {
			fmt.Println("Auto-Coder installation completed successfully!")
		} else {
			fmt.Println("Auto-Coder installation encountered errors.")
		}
	},
}

func downloadMiniconda() bool {
	var filename string
	url := ""
	switch runtime.GOOS {
	case "darwin":
		filename = "miniconda.sh"
		url = "https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-x86_64.sh"
	case "linux":
		filename = "miniconda.sh"
		url = "https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh"
	case "windows":
		filename = "miniconda.exe"
		url = "https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe"
	}

	if _, err := os.Stat(filename); err == nil {
		fmt.Printf("File %s already exists. Skipping download.\n", filename)
		return true
	}

	var out []byte
	var err error
	if runtime.GOOS == "windows" {
		out, err = exec.Command("curl", "-o", filename, url).CombinedOutput()
	} else {
		out, err = exec.Command("wget", "-O", filename, url).CombinedOutput()
	}
	fmt.Printf("%s\n", out)
	return err == nil
}

func installMiniconda() bool {
	if runtime.GOOS == "windows" {
		fmt.Println("Starting Miniconda installation...")

		// Check if miniconda.exe exists in the current directory
		if _, err := os.Stat("miniconda.exe"); os.IsNotExist(err) {
			fmt.Println("miniconda.exe not found in the current directory.")
			return false
		}

		// Launch miniconda.exe using cmd /C start
		condaPath := os.ExpandEnv("${UserProfile}\\Miniconda3")

		err := exec.Command("cmd", "/C", "start", "/wait", "", "miniconda.exe", "/InstallationType=JustMe", "/RegisterPython=0", "/S", "/D="+condaPath).Run()
		if err != nil {
			fmt.Println("Error during Miniconda installation:", err)
			return false
		}

		// Set the full path to conda.exe
		os.Setenv("CONDA_EXE", filepath.Join(condaPath, "Scripts", "conda.exe"))

		// Re-check if conda is available using the full path
		if _, err := os.Stat(os.Getenv("CONDA_EXE")); os.IsNotExist(err) {
			fmt.Println("Miniconda installation may have failed. Conda not found at:", os.Getenv("CONDA_EXE"))
			return false  
		}

		return true
	} else {
		out, err := exec.Command("bash", "miniconda.sh", "-b").CombinedOutput()
		fmt.Printf("%s\n", out)
		return err == nil
	}
}

func createEnvironment() bool {
	pythonVersion := "3.10.11"
	if runtime.GOOS == "windows" {
		pythonVersion = "3.11.9"
	}
	condaExe := "conda"
	if runtime.GOOS == "windows" {
		condaExe = os.Getenv("CONDA_EXE")
	}
	out, err := exec.Command(condaExe, "create", "--name", "auto-coder", "python="+pythonVersion, "-y").CombinedOutput()
	fmt.Printf("%s\n", out)
	return err == nil
}

func installAutoCoder() bool {
	condaExe := "conda" 
	if runtime.GOOS == "windows" {
		condaExe = os.Getenv("CONDA_EXE")
	}
	out, err := exec.Command(condaExe, "run", "-n", "auto-coder", "pip", "install", "-U", "auto-coder").CombinedOutput()
	fmt.Printf("%s\n", out)
	return err == nil
}

func startRayCluster() bool {
	condaExe := "conda"
	if runtime.GOOS == "windows" {  
		condaExe = os.Getenv("CONDA_EXE")
	}
	out, err := exec.Command(condaExe, "run", "-n", "auto-coder", "ray", "start", "--head").CombinedOutput()
	fmt.Printf("%s\n", out)
	return err == nil
}

func installStorage() bool {
	out, err := exec.Command("conda", "run", "-n", "auto-coder", "byzerllm", "storage", "start").CombinedOutput()
	fmt.Printf("%s\n", out)
	return err == nil
}
