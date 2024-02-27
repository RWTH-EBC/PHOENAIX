import time
import threading


class Test:
    def __init__(self) -> None:
        self.number = 0
    
    def run(self):
        while True:
            self.number += 1
            time.sleep(2)
        
    def run2(self):
        while True:
            print(self.number)
            time.sleep(2)
        
    def run_total(self):
        threading.Thread(target=self.run).start()
        threading.Thread(target=self.run2).start()
        
        
if __name__ == '__main__':
    t = Test()
    t.run_total()
    
    