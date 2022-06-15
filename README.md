# decoder-box 

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
```

## Install python packages ##
* pip install adafruit-io
* pip install mariadb
* pip install PyBoof
* pip install easydict
* pip install yaml2


## Configurations ##
* open config.yaml file.
* connect: change user and password values.
* client: change user and key values.
