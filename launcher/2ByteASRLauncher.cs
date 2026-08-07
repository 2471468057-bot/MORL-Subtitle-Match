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
        if (!File.Exists(pythonw) || !File.Exists(entrypoint))
        {
            string setup = Path.Combine(root, "setup_2byteasr.bat");
            DialogResult answer = MessageBox.Show(
                "2ByteASR 还没有完成首次配置。\n\n" +
                "现在自动安装运行环境并下载约 11 GB 模型吗？\n" +
                "安装过程中需要保持网络连接。",
                "2ByteASR 首次配置",
                File.Exists(setup) ? MessageBoxButtons.YesNo : MessageBoxButtons.OK,
                MessageBoxIcon.Information);
            if (answer == DialogResult.Yes && File.Exists(setup))
            {
                ProcessStartInfo setupInfo = new ProcessStartInfo();
                setupInfo.FileName = setup;
                setupInfo.WorkingDirectory = root;
                setupInfo.UseShellExecute = true;
                Process setupProcess = Process.Start(setupInfo);
                if (setupProcess != null)
                {
                    setupProcess.Dispose();
                    return 0;
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
            Process child = Process.Start(startInfo);
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
