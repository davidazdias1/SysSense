import os
import sys
import win32serviceutil
import win32service
import win32event
import servicemanager
import subprocess

class APILoggerService(win32serviceutil.ServiceFramework):
    _svc_name_ = "Z_SYSSENSE_API"
    _svc_display_name_ = "Z Syssense - API Logger"
    _svc_description_ = "Serviço FastAPI com Uvicorn para o sistema ProdSense"

    def __init__(self, args):
        super().__init__(args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.process = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        if self.process:
            self.process.terminate()
        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        servicemanager.LogInfoMsg("API Logger Service iniciado.")

        api_dir = r"C:\PRODSENSE\API"

        # Acrescenta o diretório ao PYTHONPATH
        env = os.environ.copy()
        env["PYTHONPATH"] = api_dir + os.pathsep + env.get("PYTHONPATH", "")

        self.process = subprocess.Popen([
            sys.executable, "-m", "uvicorn", "api_logger:app", "--host", "127.0.0.1", "--port", "8000"
        ], cwd=api_dir, env=env)

        win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)

if __name__ == '__main__':
    win32serviceutil.HandleCommandLine(APILoggerService)
