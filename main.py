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
        self.last_idx = None
        self.mode = Reader.mode[mode]
        self.clock = time()
        
    def data_reader(self):
        self.my_api.read()
        self.my_api.aio.send('debug', 'O equipamento está funcionando!')
        
        cap = cv2.VideoCapture(0)
        self.led.on()
        self.data = []
        self.clock = time() - 5
        while True:
            dtime = time() - self.clock
            state = dtime % 2 <= 1
            print('\rdtime {:.2f}\tstate: {}\t'.format(dtime, state), end='')
            _, img = cap.read()
            img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
            if dtime > 5:
                if state:
                    self.rfid_reader()
                else:
                    self.qrcode_reader(img)
            #cv2.imshow("code detector", img)
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
        
        cap = cv2.VideoCapture(0)
        self.led.blink(0.5, 0.5)        
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
            #cv2.imshow("code detector", img)
            if cv2.waitKey(1) == ord("q") or data:
                print(f'\nLeitura QRcode: {data}')
                self.buzz.beep(0.5, 1, 1)
                self.my_api.aio.send('debug', 'QRcode está funcionando!')
                break
        cap.release()
        cv2.destroyAllWindows()
        
        try:
            idx, test = self.rfid.read()
            idx = str(idx)
            print(f'\nLeitura RFID: {idx}')
            self.buzz.beep(0.5, 1, 1)
            self.my_api.aio.send('debug', 'RFID está funcionando!')
        except:
            print('RFID não está funcionando!')
    
    def qrcode_reader(self, img):
        try:
            pb_img = pb.ndarray_to_boof(img)
            self.detector.detect(pb_img)
            data = []
            for qr in self.detector.detections:
                data.append(qr.message)
        except:
            data = None
            print('\nFalha na leitura do QRcode!')
        
        if data:
            self.data += data
            print(f'\nLeitura QRcode: {data}')
            self.buzz.beep(0.5, 1, 1)
            self.clock = time()
    
    def rfid_reader(self):
        try:
            idx, _ = self.rfid.read_no_block()
        except:
            idx = None 
            print('\nFalha na leitura do RFID!')
        
        if idx:
            idx = str(idx)
            print(f'\nLeitura RFID: {idx}')
            self.buzz.beep(0.5, 1, 1)
            if idx == self.last_idx:
                print(f'\nDevolução: {idx} {self.data}')
                self.deregister(idx, self.data)
                self.data = []
                self.last_idx = None
            elif self.data:
                print(f'\nEmprestimo: {idx} {self.data}')
                self.register(idx, self.data)
                self.data = []
            else:
                self.last_idx = idx
            self.clock = time()
    
    def register(self, rfid, qrcode):
        text = f'rfid={rfid}'
        table_name, data = self.my_api.commands(text, 'select', False)
        aluno_id, aluno_nome = str(data[0][0]), data[0][2]
        
        text = f'alunos_fk={aluno_id}&done=False'
        table_name, data = self.my_api.commands(text, 'select', False)
        if not data:
            table_name, data = self.my_api.commands(text, 'insert', False)
        registro_id = str(data[-1][0])
        
        text = 'qrcode='+';'.join(qrcode)
        table_name, data = self.my_api.commands(text, 'select', False)
        materiais = {str(x[0]):x[2] for x in data}
        
        reg_list = [registro_id]
        mat_list = list(materiais.keys())
        product_list = list(product(reg_list, mat_list))
        reg_list = [x[0] for x in product_list]
        mat_list = [x[1] for x in product_list]
        text = 'registros_fk='+';'.join(reg_list) + '&materiais_fk=' + ';'.join(mat_list) 
        table_name, data = self.my_api.commands(text, 'insert', False)
        
        alunos_values = ';'.join([aluno_nome])
        materiais_values = ';'.join(materiais.values())
        self.my_api.aio.send('registros', f'Empréstimo alunos={alunos_values}&materiais={materiais_values}')
    
    def deregister(self, rfid, qrcode):
        text = f'rfid={rfid}'
        table_name, data = self.my_api.commands(text, 'select', False)
        aluno_id, aluno_nome = str(data[0][0]), data[0][2]
        
        text = f'alunos_fk={aluno_id}&done=False'
        table_name, data = self.my_api.commands(text, 'select', False)
        if not data:
            self.my_api.aio.send('registros', f'Devolução alunos={aluno_nome}&materiais=')
            return 
        registro_id = str(data[-1][0])
        
        if qrcode:
            text = 'qrcode='+';'.join(qrcode)
            table_name, data = self.my_api.commands(text, 'select', False)
            qrcode_materiais = {str(x[0]):x[2] for x in data}
        else:
            qrcode_materiais = {}
        
        text = f"registros_fk={registro_id}"
        table_name, data = self.my_api.commands(text, 'select', False)
        listas = {str(x[0]):str(x[2]) for x in data}
        materiais_id = list(listas.values())
        
        table_name ='tb_materiais'
        data = {'materiais_id':materiais_id}
        data = self.my_api.select(table_name, data)
        db_materiais = {str(x[0]):x[2] for x in data}
        
        done = True
        if not qrcode_materiais:
            materiais = db_materiais
        else:
            for key in db_materiais:
                if key not in qrcode_materiais:
                    done = False
            materiais = qrcode_materiais
        
        if done:
            text = f'alunos_fk={aluno_id}&done=False:True'
            table_name, data = self.my_api.commands(text, 'update', False)
        
        alunos_values = ';'.join([aluno_nome])
        materiais_values = ';'.join(materiais.values())
        self.my_api.aio.send('registros', f'Devolução alunos={alunos_values}&materiais={materiais_values}')
    
        
if __name__ == '__main__':
    GPIO.cleanup()
    reader = Reader()
    reader.test_reader()
    reader.data_reader()
    