import RPi.GPIO as GPIO
from mfrc522 import SimpleMFRC522
from gpiozero import Buzzer, LED
from time import sleep, time
import pyboof as pb
import cv2
import numpy as np

from api import API
from itertools import product

class Reader:
    mode = {0:'qrcode', 1:'micro qrcode'}
    
    def __init__(self, mode=1):
        self.my_api = API('config.yaml')
        self.rfid = SimpleMFRC522()
        self.buzz = Buzzer(17)
        self.led = LED(26)
        if mode == 0:
            self.detector = pb.FactoryFiducial(np.uint8).qrcode()
        else:
            self.detector = pb.FactoryFiducial(np.uint8).microqr()
        self.data = []
        self.mode = Reader.mode[mode]
        self.clock = time()
        
    def data_reader(self):
        cap = cv2.VideoCapture(0)
        while True:
            dtime = time() - self.clock
            state = dtime % 3 <= 1
            print('\rdtime {:.2f}\tstate: {}\t'.format(dtime, state), end='')
            _, img = cap.read()
            img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
            if dtime > 5:
                if state:
                    self.rfid_reader()
                else:
                    self.qrcode_reader(img)
            cv2.imshow("code detector", img)
            if cv2.waitKey(1) == ord("q"):
                break
        cap.release()
        cv2.destroyAllWindows()
        GPIO.cleanup()
    
    def test_reader(self):
        self.led.off()
        try:
            self.my_api.aio.send('debug', f'O equipamento foi ligado no modo {self.mode}!')
        except:
            print('Adafruit IO não está funcionando!')
        
        self.led.blink(0.5, 0.5)        
        
        cap = cv2.VideoCapture(0)
        while True:
            _, img = cap.read()
            img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
            try:
                pb_img = pb.ndarray_to_boof(img)
                self.detector.detect(pb_img)
                data = []
                for qr in self.detector.detections:
                    data.append(qr.message)
            except:
                print('QRcode não está funcionando!')
            cv2.imshow("code detector", img)
            if cv2.waitKey(1) == ord("q") or data:
                self.buzz.beep(0.5, 1, 1)
                self.my_api.aio.send('debug', 'QRcode está funcionando!')
                break
        cap.release()
        cv2.destroyAllWindows()
        
        try:
            idx, test = self.rfid.read()
            self.buzz.beep(0.5, 1, 1)
            self.my_api.aio.send('debug', 'RFID está funcionando!')
        except:
            print('RFID não está funcionando!')
               
        self.led.on()
        self.my_api.aio.send('debug', 'O equipamento está funcionando!')
        self.data = []
        self.clock = time()
    
    def qrcode_reader(self, img):
        try:
            pb_img = pb.ndarray_to_boof(img)
            self.detector.detect(pb_img)
            data = []
            for qr in self.detector.detections:
                data.append(qr.message)
        except:
            data, bbox = None, None
            print('\nFalha na leitura do QRcode!')
        if data:
            self.data += data
            print(f'\nLeitura QRcode: {data}')
            self.buzz.beep(0.5, 1, 1)
            self.clock = time()
    
    def rfid_reader(self):
        try:
            idx, text = self.rfid.read_no_block()
        except:
            idx, text = None, None 
            print('\nFalha na leitura do RFID!')
        if idx:
            if self.data:
                alunos, materiais = self.register([idx], self.data)
            else:
                alunos, materiais = self.deregister([idx])
            self.data = []
            self.buzz.beep(0.5, 1, 1)
            self.clock = time()
    
    def register(self, rfid, qrcode):
        text = 'rfid='+';'.join(rfid)
        table_name, old_data = self.my_api.commands(text, 'select', False)
        alunos = {str(x[0]):x[2] for x in old_data}
        
        text = 'alunos_fk='+';'.join(alunos.keys()) + '&done=' + '; '.join(['0' for _ in alunos]) 
        table_name, new_data = self.my_api.commands(text, 'insert', True)
        registros = [str(x[0]) for x in new_data]
        
        text = 'qrcode='+';'.join(qrcode)
        table_name, old_data = self.my_api.commands(text, 'select', False)
        materiais = {str(x[0]):x[2] for x in old_data}
        
        reg_list = registros.copy()
        mat_list = list(materiais.keys())
        product_list = list(product(reg_list, mat_list))
        reg_list = [x[0] for x in product_list]
        mat_list = [x[1] for x in product_list]
        text = 'registros_fk='+';'.join(reg_list) + '&materiais_fk=' + ';'.join(mat_list) 
        table_name, new_data = self.my_api.commands(text, 'insert', True)
        listas = [str(x[0]) for x in new_data]
        
        alunos_values = ';'.join(alunos.values())
        materiais_values = ';'.join(materiais.values())
        self.my_api.aio.send('registros', f'register alunos={alunos_values}&materiais={materiais_values}')
    
    def deregister(self, rfid):
        text = 'rfid='+';'.join(rfid)
        table_name, old_data = self.my_api.commands(text, 'select', False)
        alunos = {str(x[0]):x[2] for x in old_data}
        
        text = 'alunos_fk='+';'.join(alunos.keys()) + '&done=' + '; '.join(['0:1' for _ in alunos]) 
        table_name, new_data = self.my_api.commands(text, 'update', True)
        registros = [str(x[0]) for x in new_data]
        
        reg_list = registros.copy()
        mat_list = ["'*'"]
        product_list = list(product(reg_list, mat_list))
        reg_list = [x[0] for x in product_list]
        mat_list = [x[1] for x in product_list]
        text = 'registros_fk='+';'.join(reg_list) + '&materiais_fk=' + ';'.join(mat_list) 
        table_name, new_data = self.my_api.commands(text, 'select', False)
        listas = [str(x[0]) for x in new_data]
        
        text = 'registros_fk='+';'.join(registros) + '&materiais_fk=' + '; '.join(['0:1' for _ in alunos]) 
        table_name ='tb_listas'
        reg_list = list(registros.keys())
        new_data = {'listas_registros_fk':reg_list,
                    'listas_materiais_fk':'*'}
        new_data = self.my_api.select(table_name, new_data)
        materiais = list({str(x[2]) for x in new_data})
        
        table_name ='tb_materiais'
        data = {'materiais_id':materiais}
        old_data = self.my_api.select(table_name, data)
        materiais = {str(x[0]):x[2] for x in old_data}
        
        alunos_values = ';'.join(alunos.values())
        materiais_values = ';'.join(materiais.values())
        self.my_api.aio.send('registros', f'deregister alunos={alunos_values}&materiais={materiais_values}')
    
        
if __name__ == '__main__':
    GPIO.cleanup()
    reader = Reader()
    reader.test_reader()
    reader.data_reader()