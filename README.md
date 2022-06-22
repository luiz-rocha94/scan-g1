# scan-g1

## mfrc522
https://www.arduinoecia.com.br/modulo-rfid-mfrc522-com-raspberry-pi-4/

## Raspberry Cam v2
https://www.hackster.io/gatoninja236/scan-qr-codes-in-real-time-with-raspberry-pi-a5268b

## Install MariaDB.
* sudo apt install mariadb-server
* sudo mysql_secure_installation
* sudo apt-get install libmariadb3
* sudo apt-get install libmariadbclient-dev

### run MariaDB. 
* sudo mariadb

### Create database and tables, change user and password.
```
GRANT ALL ON *.* TO 'user'@'localhost' IDENTIFIED BY 'password' WITH GRANT OPTION;

CREATE DATABASE `db_registros`;

USE `db_registros`;

CREATE TABLE `tb_alunos` (`alunos_id` SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
                          `alunos_rfid` BIGINT UNSIGNED NOT NULL UNIQUE,
                          `alunos_nome` VARCHAR(100) NOT NULL UNIQUE,
                           PRIMARY KEY (`alunos_id`)
                         );

CREATE TABLE `tb_materiais` (`materiais_id` MEDIUMINT UNSIGNED NOT NULL AUTO_INCREMENT,
                             `materiais_qrcode` VARCHAR(50) NOT NULL UNIQUE,
                             `materiais_desc` VARCHAR(200) NOT NULL,
                              PRIMARY KEY (`materiais_id`),
                              UNIQUE (`materiais_qrcode`, `materiais_desc`)
                             );

CREATE TABLE `tb_registros` (`registros_id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
                             `registros_alunos_fk` SMALLINT UNSIGNED NOT NULL,
                             `registros_done` BOOL NOT NULL DEFAULT 0,
                             `registros_open` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP(), 
                             `registros_close` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP() ON UPDATE CURRENT_TIMESTAMP(),
                              PRIMARY KEY (`registros_id`),
                              FOREIGN KEY (`registros_alunos_fk`) REFERENCES `tb_alunos` (`alunos_id`) ON UPDATE CASCADE ON DELETE CASCADE
                            );

CREATE TABLE `tb_listas` (`listas_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                          `listas_registros_fk` INT UNSIGNED NOT NULL,
                          `listas_materiais_fk` MEDIUMINT UNSIGNED NOT NULL,
                           PRIMARY KEY (`listas_id`),
                           FOREIGN KEY (`listas_registros_fk`) REFERENCES `tb_registros` (`registros_id`) ON UPDATE CASCADE ON DELETE CASCADE,
                           FOREIGN KEY (`listas_materiais_fk`) REFERENCES `tb_materiais` (`materiais_id`) ON UPDATE CASCADE ON DELETE CASCADE
                         );

CREATE VIEW tb_view AS SELECT listas_id, alunos_nome, materiais_desc FROM (((tb_alunos INNER JOIN tb_registros ON tb_alunos.alunos_id = tb_registros.registros_alunos_fk) INNER JOIN tb_listas ON tb_registros.registros_id = tb_listas.listas_registros_fk) INNER JOIN tb_materiais
on tb_listas.listas_materiais_fk = tb_materiais.materiais_id) where registros_done = False';
```

## Install python packages
* pip install adafruit-io
* pip install mariadb
* pip install PyBoof
* pip install easydict
* pip install yaml2


## Configurations
* open config.yaml file.
* connect: change user and password values.
* client: change user and key values.


## Run on start up
https://medium.com/codex/how-to-run-a-python-program-at-startup-on-your-raspberry-pi-d5cc1730d4db

