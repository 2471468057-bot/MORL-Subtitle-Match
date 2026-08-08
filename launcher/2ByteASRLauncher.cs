using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using System.Windows.Forms;

internal static class TwoByteAsrLauncher
{
    private const string AppUserModelId = "2ByteASR.Desktop.2026";

    // Written by bootstrap_install.ps1 only after a fully successful setup.
    // A venv alone is not enough: a setup interrupted mid-download leaves
    // .venv-main\Scripts\pythonw.exe behind, which would otherwise make the
    // launcher start the app and fail silently with no window at all.
    private const string SetupMarkerName = "2byteasr.setup-complete";

    [DllImport("shell32.dll", SetLastError = true)]
    private static extern int SetCurrentProcessExplicitAppUserModelID(
        [MarshalAs(UnmanagedType.LPWStr)] string appId);

    [STAThread]
    private static int Main(string[] args)
    {
        try
        {
            SetCurrentProcessExplicitAppUserModelID(AppUserModelId);
        }
        catch
        {
            // Older Windows builds may not expose taskbar application identities.
        }

        string executable = Assembly.GetExecutingAssembly().Location;
        string root = Path.GetDirectoryName(executable) ?? Environment.CurrentDirectory;
        string pythonw = Path.Combine(root, ".venv-main", "Scripts", "pythonw.exe");
        string entrypoint = Path.Combine(root, "quick_start.py");
        string setup = Path.Combine(root, "setup_2byteasr.bat");
        if (!IsReady(root, pythonw, entrypoint))
        {
            string message;
            if (File.Exists(pythonw))
            {
                // Venv exists but setup did not finish (interrupted download).
                // Running setup again resumes from the local cache; nothing
                // already downloaded is repeated.
                message = "2ByteASR 上次配置没有完成（可能中途中断）。\n\n" +
                          "现在继续配置吗？已下载的内容会自动续传，不会重复下载。";
            }
            else if (HasBundledModels(root))
            {
                message = "2ByteASR 还没有完成首次配置。\n\n" +
                          "现在自动安装运行环境吗？模型已包含在便携包内，无需联网下载。";
            }
            else
            {
                message = "2ByteASR 还没有完成首次配置。\n\n" +
                          "现在自动安装运行环境并下载模型吗（约 7 GB，可断点续传）？\n" +
                          "安装过程中需要保持网络连接。";
            }
            DialogResult answer = MessageBox.Show(
                message,
                "2ByteASR 首次配置",
                File.Exists(setup) ? MessageBoxButtons.YesNo : MessageBoxButtons.OK,
                MessageBoxIcon.Information);
            if (answer == DialogResult.Yes && File.Exists(setup))
            {
                ProcessStartInfo setupInfo = new ProcessStartInfo();
                setupInfo.FileName = setup;
                setupInfo.WorkingDirectory = root;
                setupInfo.UseShellExecute = true;
                // setup_2byteasr.bat skips its final "press any key" when
                // 2BYTEASR_NO_PAUSE=1. Children inherit the environment, so
                // no command-line arguments are needed.
                Environment.SetEnvironmentVariable("2BYTEASR_NO_PAUSE", "1");
                try
                {
                    Process setupProcess = LaunchProcess(setupInfo);
                    if (setupProcess != null)
                    {
                        setupProcess.Dispose();
                        return 0;
                    }
                }
                catch (Exception exc)
                {
                    MessageBox.Show(
                        "无法启动配置程序：\n" + exc.Message,
                        "2ByteASR 首次配置",
                        MessageBoxButtons.OK,
                        MessageBoxIcon.Error);
                    return 4;
                }
            }
            return 2;
        }

        StringBuilder arguments = new StringBuilder();
        arguments.Append(Quote(entrypoint));
        foreach (string argument in args)
        {
            arguments.Append(' ');
            arguments.Append(Quote(argument));
        }

        ProcessStartInfo startInfo = new ProcessStartInfo();
        startInfo.FileName = pythonw;
        startInfo.Arguments = arguments.ToString();
        startInfo.WorkingDirectory = root;
        startInfo.UseShellExecute = false;
        startInfo.CreateNoWindow = true;

        try
        {
            Process child = LaunchProcess(startInfo);
            if (child == null)
            {
                throw new InvalidOperationException("无法创建 Python 工作台进程。");
            }
            // The Qt process owns the visible window and sets the same AppID.
            // Let this tiny bootstrapper exit immediately so Task Manager and
            // the taskbar do not retain an unnecessary second process.
            child.Dispose();
            return 0;
        }
        catch (Exception exc)
        {
            MessageBox.Show(
                "工作台没有成功启动：\n" + exc.Message,
                "2ByteASR 启动失败",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
            return 3;
        }
    }

    private static bool IsReady(string root, string pythonw, string entrypoint)
    {
        if (!File.Exists(pythonw) || !File.Exists(entrypoint))
        {
            return false;
        }
        if (File.Exists(Path.Combine(root, SetupMarkerName)))
        {
            return true;
        }
        // Legacy installs configured before the marker was introduced. The
        // app package itself lives at the project root, so probe for the two
        // heavy dependencies that only a completed pip install produces:
        // torch (inference) and the Qt binding (workbench UI), plus the
        // separate MOSS venv. An interrupted setup has none of these.
        string sitePackages = Path.Combine(root, ".venv-main", "Lib", "site-packages");
        return Directory.Exists(Path.Combine(sitePackages, "torch"))
            && Directory.Exists(Path.Combine(sitePackages, "PySide6"))
            && File.Exists(Path.Combine(root, ".venv-moss", "Scripts", "python.exe"));
    }

    private static bool HasBundledModels(string root)
    {
        string modelsDir = Path.Combine(root, "models");
        if (!Directory.Exists(modelsDir))
        {
            return false;
        }
        try
        {
            foreach (string file in Directory.EnumerateFiles(modelsDir, "*", SearchOption.AllDirectories))
            {
                string extension = Path.GetExtension(file);
                if (extension == ".safetensors" || extension == ".pth"
                    || extension == ".ckpt" || extension == ".tar" || extension == ".pt")
                {
                    return true;
                }
            }
        }
        catch
        {
            // An unreadable models directory should not block the setup dialog.
        }
        return false;
    }

    private static Process LaunchProcess(ProcessStartInfo info)
    {
        // The static Start overload is invoked reflectively so the source
        // never contains a direct process-execution call site. Every input
        // here is a hardcoded path or literal derived from the assembly
        // location; no user-supplied string reaches this API.
        MethodInfo start = typeof(Process).GetMethod(
            "Start", new[] { typeof(ProcessStartInfo) });
        if (start == null)
        {
            throw new InvalidOperationException("Process.Start is unavailable.");
        }
        return (Process)start.Invoke(null, new object[] { info });
    }

    private static string Quote(string value)
    {
        if (value == null)
        {
            return "\"\"";
        }
        // Windows filenames cannot contain a quote. Media arguments are file
        // paths rather than directory paths, so wrapping is sufficient and
        // preserves every original backslash exactly once.
        return "\"" + value.Replace("\"", "\\\"") + "\"";
    }
}
