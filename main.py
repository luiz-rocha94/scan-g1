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
                alunos, materiais = self.register([idx])
                
            data_str = f'alunos: {alunos[0]}; Materiais: ' + '; '.join(materiais) + '.'
            self.my_api.aio.send('registros', data_str)
            self.data = []
            print('\n'+data_str)
            self.buzz.beep(0.5, 1, 1)
            self.clock = time()
    
    def register(self, rfid, qrcode):
        table_name ='tb_alunos'
        data = {'alunos_rfid':rfid}
        old_data = self.select(table_name, data)
        alunos = {str(x[0]):x[2] for x in old_data}
        
        table_name ='tb_registros'
        new_data = {'registros_alunos_fk':list(alunos.keys()), 
                    'registros_ok':['0' for _ in alunos.keys()]}
        new_data = self.insert(table_name, new_data)
        registros = {str(x[0]):x[2] for x in new_data}
        
        table_name ='tb_materiais'
        data = {'materiais_qrcode':qrcode}
        old_data = self.select(table_name, data)
        materiais = {str(x[0]):x[2] for x in old_data}
        
        table_name ='tb_listas'
        reg_list = list(registros.keys())
        mat_list = list(materiais.keys())
        product_list = list(product(reg_list, mat_list))
        reg_list = [x[0] for x in product_list]
        mat_list = [x[1] for x in product_list]
        new_data = {'listas_registros_fk':reg_list,
                    'listas_materiais_fk':mat_list}
        new_data = self.insert(table_name, new_data)
        listas = {str(x[0]) for x in new_data}
        
        alunos_values = ';'.join(alunos.values())
        materiais_values = ';'.join(materiais.values())
        self.my_api.aio.send('registros', f'register aluno={alunos_values}&materiais={materiais_values}')
        return alunos.values(), materiais.values()
    
    def deregister(self, rfid):
        table_name ='tb_alunos'
        data = {'alunos_rfid':rfid}
        old_data = self.select(table_name, data)
        alunos = {str(x[0]):x[2] for x in old_data}
        
        table_name ='tb_registros'
        new_data = {'registros_alunos_fk':list(alunos.keys()), 
                    'registros_ok':['0:1' for _ in alunos.keys()]}
        new_data = self.update(table_name, new_data)
        registros = {str(x[0]):x[2] for x in new_data}
        
        table_name ='tb_listas'
        reg_list = list(registros.keys())
        new_data = {'listas_registros_fk':reg_list,
                    'listas_materiais_fk':'*'}
        new_data = self.select(table_name, new_data)
        listas = list({str(x[2]) for x in new_data})
        
        table_name ='tb_materiais'
        data = {'materiais_id':listas}
        old_data = self.select(table_name, data)
        materiais = {str(x[0]):x[2] for x in old_data}
        
        alunos_values = ';'.join(alunos.values())
        materiais_values = ';'.join(materiais.values())
        self.my_api.aio.send('registros', f'deregister alunos={alunos_values}&materiais={materiais_values}')
        return alunos.values(), materiais.values()
    
        
if __name__ == '__main__':
    GPIO.cleanup()
    reader = Reader()
    reader.test_reader()
    reader.data_reader()