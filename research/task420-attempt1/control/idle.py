import signal,time,os
def reap(*args):
 try:
  while os.waitpid(-1,os.WNOHANG)[0]:pass
 except ChildProcessError:pass
signal.signal(signal.SIGCHLD,reap)
while True:time.sleep(1)
