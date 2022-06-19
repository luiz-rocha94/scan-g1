# -*- coding: utf-8 -*-
"""
Created on Sun Jun  5 21:13:13 2022

@author: rocha
"""
import mariadb
import re
import yaml
from easydict import EasyDict
from pathlib import Path
from Adafruit_IO import Client
from datetime import datetime, timezone
from time import sleep

from threading import Thread
from queue import Queue

from multiprocessing import Process

def merge_new_config(config, new_config):
    for key, val in new_config.items():
        if not isinstance(val, dict):
            config[key] = val
            continue
        if key not in config:
            config[key] = EasyDict()
        merge_new_config(config[key], val)
    return config


def cfg_from_yaml_file(cfg_file):
    config = EasyDict()
    config.ROOT_DIR = Path(__file__).resolve().parent
    with open(cfg_file, 'r') as f:
        try:
            new_config = yaml.safe_load(f, Loader=yaml.FullLoader)
        except:
            new_config = yaml.safe_load(f)
        merge_new_config(config=config, new_config=new_config)
    return config


class API:
    def __init__(self, cfg_file):
        self.cfg = cfg_from_yaml_file(cfg_file)     
        self.connect()
    
    def connect(self):
        conn = mariadb.connect(user=self.cfg.connect.user,
                               password=self.cfg.connect.password,
                               host=self.cfg.connect.host,
                               port=self.cfg.connect.port,
                               database=self.cfg.connect.database)
        self.conn = conn
        self.cur = conn.cursor()
        
        aio = Client(self.cfg.client.user, self.cfg.client.key)
        aio.feeds('api.select')
        self.aio = aio
    
    def disconnect(self):
        self.conn.close()
    
    def execute(self, text):
        print(text)
        if ':' in text:
            raise Exception("':' in text")
        
        try:
            self.cur.execute(text)
        except mariadb.Error as e:
            print(f"Error connecting to MariaDB Platform: {e}")
            raise Exception("cur.execute(text)")
    
    def transform(self, text):
        """
        text = column_0=value_0;value_1:value_2&column_1=value_3;value_4:value_5
        table_name = cfg.tables[column_0]
        data = {cfg.database[table_name][column_0]:['value_0', 'value_1':'value_2'], 
                cfg.database[table_name][column_1]:[value_3, value_4:value_5]}
        """
        str_f = lambda x: re.sub(' +', ' ', x).strip().lower()
        data_f = lambda x: {str_f(y.split('=')[0]):[str_f(z) for z in y.split('=')[1].split(';')] 
                            for y in x.split('&')}
        errors = []        
        if '=' not in text:
            errors.append("'=' not in text")
        if text.count('=') != (text.count('&') + 1):
            errors.append("text.count('=') != (text.count('&') + 1)")
        if text.count(';') % max(text.count('='), 1) != 0:
            errors.append("text.count(';') % text.count('=') != 0")
        if errors:
            raise Exception('; '.join(errors))
        
        data = data_f(text)
        for key in data:
            if not self.cfg.tables.get(key):
                errors.append(f"not cfg.tables.get({key})")
            if '' in data[key]:
                errors.append(f"'' in data[{key}]")        
        if errors:
            raise Exception('; '.join(errors))
        
        keys = list({self.cfg.tables[key] for key in data.keys()})
        if len(keys) != 1:
            errors.append("len(keys) != 1")
        
        for table_name in keys:
            table_cfg = self.cfg.database[table_name]
            for key in data:
                if table_cfg.get(key):
                    if table_cfg[key].unique:
                        if len(data[key]) != len(set(data[key])):
                            errors.append(f"len(data[{key}]) != len(set(data[{key}]))")
        if errors:
            raise Exception('; '.join(errors))
                
        table_name = keys[0]
        table_cfg = self.cfg.database[table_name]
        values_f = lambda key, values: [f"'{x}'".replace(':', "':'") if table_cfg[key].type == 'str' else x 
                                        for x in values]
        data = {table_cfg[key].name: values_f(key, values) for key, values in data.items()}
        return table_name, data
    
    def insert(self, table_name, data):
        table_cfg = self.cfg.database[table_name]  
        table_keys = sorted([table_cfg[key].name for key in table_cfg.keys() if key != 'id'])
        data_keys = sorted(data.keys())
        if table_keys != data_keys:
            raise Exception('table_keys != data_keys')
        
        columns = ', '.join(data.keys())
        values = ', '.join(['(' + ', '.join(x) + ')' 
                            for x in zip(*data.values())])
        new_text = f'INSERT INTO {table_name} ({columns}) VALUES {values}'
        self.execute(new_text)
        self.conn.commit()
        return self.select(table_name, data)
    
    def update(self, table_name, data):
        case = lambda x, id0, id1: [y.split(':')[id0] if ':' in y else [y,''][id1] 
                                    for y in x] 
        old_data = self.select(table_name, {key:case(values,0,0) for key, values in data.items()})
        ids = [str(x[0]) for x in old_data]
        table_cfg = self.cfg.database[table_name]
        condition = table_cfg.id.name+' IN (' + ' ,'.join(ids) + ')'
        update_f = lambda key, value: f'when {table_cfg.id.name} = {key} then {value}'
        columns_values = ', '.join([key + ' = ' +
                                    '(case ' + 
                                    ' '.join([update_f(id, value) 
                                              for id, value in zip(ids, case(values,1,1)*len(ids)) if value]) + 
                                    ' end)' 
                                    for key, values in data.items() 
                                    if [value for value in values if ':' in value]])
        new_text = f'UPDATE {table_name} SET {columns_values} WHERE {condition}'
        self.execute(new_text)
        self.conn.commit()
        return self.select(table_name, {key:case(values,1,0) for key, values in data.items()})
    
    def delete(self, table_name, data):
        old_data = self.select(table_name, data)
        ids = [str(x[0]) for x in old_data]
        table_cfg = self.cfg.database[table_name]
        condition = table_cfg.id.name+' IN (' + ' ,'.join(ids) + ')'
        new_text = f'DELETE FROM {table_name} WHERE {condition}'
        self.execute(new_text)
        self.conn.commit()
        return old_data
    
    def select(self, table_name, data):
        condition = ' AND '.join([key+' IN (' + ' ,'.join(values) + ')' 
                                  for key, values in data.items() if "'*'" not in values])
        if condition:
            new_text = f'SELECT * FROM {table_name} WHERE {condition}'
        else:
            new_text = f'SELECT * FROM {table_name}'
        self.execute(new_text)
        new_data = [x for x in self.cur.fetchall()]
        return new_data
    
    def commands(self, text, mode, send=True):
        response = ''
        try:
            table_name, data = self.transform(text)
            if mode == 'insert':
                new_data = self.insert(table_name, data)
            elif mode == 'update':
                new_data = self.update(table_name, data)
            elif mode == 'delete':
                new_data = self.delete(table_name, data)
            else:
                new_data = self.select(table_name, data)
            
            table_cfg = self.cfg.database[table_name]  
            keys = ', '.join([key for key in table_cfg.keys()][1:3])
            values = [x[1:] for x in new_data]
            response = f'{mode} {keys} {values}'
        except Exception as e:
            print(e)
            response = str(e)
        
        if send:
            self.aio.send('api.response', response)
            
        return table_name, new_data
    
    def feeds(self, mode):
        if mode == 'insert':
            data = self.aio.receive('api.insert')
        elif mode == 'update':
            data = self.aio.receive('api.update')
        elif mode == 'delete':
            data = self.aio.receive('api.delete')
        else:
            data = self.aio.receive('api.select')
        return data
    
    def listen(self):
        mode = self.q.get()
        print(mode)
        while True:
            data = self.feeds(mode)
            created_time = datetime.strptime(data.created_at+'+0000',
                                             '%Y-%m-%dT%H:%M:%SZ%z')
            if created_time > self.last_time:
                self.last_time = created_time
                text = data.value
                self.commands(text, mode)
            sleep(1)
        self.q.task_done()
    
    
    def read(self):
        data = self.feeds('select')
        last_time = datetime.strptime(data.created_at+'+0000',
                                      '%Y-%m-%dT%H:%M:%SZ%z')
        for mode in ['insert', 'update', 'delete']:
            data = self.feeds(mode)
            created_time = datetime.strptime(data.created_at+'+0000',
                                             '%Y-%m-%dT%H:%M:%SZ%z')
            if created_time > last_time:
                last_time = created_time

        self.last_time = last_time        
        self.q = Queue()
        for mode in ['insert', 'update', 'delete', 'select']:
            self.q.put(mode)
            worker = Thread(target=self.listen)
            worker.daemon = True
            worker.start()
                
        self.q.join()

if __name__ == '__main__':
    my_api = API('config.yaml')   
    
    p1 = Process(target=my_api.read)
    p1.start()
    p1.join()
    
"""
#text = 'alunos=Luiz schitz;Rocha&rfid=5657511;1245454'
text = my_api.feeds('insert')
my_api.commands(text, 'insert')
text = my_api.feeds('select')
my_api.commands(text, 'select')
text = my_api.feeds('update')
my_api.commands(text, 'update')
text = my_api.feeds('delete')
my_api.commands(text, 'delete')
#my_api.disconnect()
"""
