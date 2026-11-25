"""Persistent official 3DGS worker. Camera poses are expressed in industrial coordinates."""
import json
import select
import subprocess
import sys
import threading
from .settings import ROOT,PROJECT
from .validation import require,transform_check


def camera_check(b):
    transform_check(b.get('camera_world'))
    for key in ('width','height'):
        require(isinstance(b.get(key),int) and 64<=b[key]<=1440,'渲染尺寸必须在 64–1440 像素内。')
    require(isinstance(b.get('fov'),(int,float)) and 10<=b['fov']<=120,'垂直视场角无效。')


class RoamClient:
    def __init__(self):self.process=None;self.lock=threading.Lock()
    def render(self,request):
        with self.lock:
            if self.process is None or self.process.poll() is not None:
                (ROOT/'.jobs').mkdir(exist_ok=True)
                self.log=open(ROOT/'.jobs/roam_worker.log','a',buffering=1)
                self.process=subprocess.Popen([sys.executable,'-X','faulthandler','-m','m0.roam_worker'],cwd=PROJECT,
                    stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.log,text=True,bufsize=1)
            self.process.stdin.write(json.dumps(request)+'\n');self.process.stdin.flush()
            if not select.select([self.process.stdout],[],[],60)[0]:
                self.process.kill();self.process.wait();raise ValueError('高斯渲染超时；标注已保留，请重试。')
            line=self.process.stdout.readline()
            if not line:raise ValueError('高斯渲染进程退出；请检查 .jobs/roam_worker.log。')
            result=json.loads(line)
            if 'error' in result:raise ValueError(result['error'])
            return result
