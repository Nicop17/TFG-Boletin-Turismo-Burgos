DROP TABLE Nivel6;
DROP TABLE Nivel5;
DROP TABLE Nivel4;
DROP TABLE Nivel3;
DROP TABLE Nivel2;
DROP TABLE Nivel1;

CREATE TABLE Nivel1 (
    ID_Nivel1 INT PRIMARY KEY,
    Nombre_Nivel1 VARCHAR(100) NOT NULL
);

INSERT INTO Nivel1 (ID_Nivel1, Nombre_Nivel1) VALUES
(1, 'Anthropomo'),
(2, 'Lithomo'),
(3, 'Hydromo'),
(4, 'Phytomo');

-- Nivel 2
CREATE TABLE Nivel2 (
    ID_Nivel2 INT PRIMARY KEY,
    Nombre_Nivel2 VARCHAR(150) NOT NULL,
    ID_Nivel1 INT NOT NULL,
    FOREIGN KEY (ID_Nivel1) REFERENCES Nivel1(ID_Nivel1)
);

INSERT INTO Nivel2 (ID_Nivel2, Nombre_Nivel2, ID_Nivel1) VALUES
(1, 'Comercio', 1),
(2, 'Hostelería', 1),
(3, 'Histórico y cultural', 2),
(4, 'Urbanismo', 2),
(5, 'Naturaleza', 3),
(6, 'Naturaleza', 4);

-- Nivel 3
CREATE TABLE Nivel3 (
    ID_Nivel3 INT PRIMARY KEY,
    Nombre_Nivel3 VARCHAR(150) NOT NULL,
    ID_Nivel2 INT NOT NULL,
    FOREIGN KEY (ID_Nivel2) REFERENCES Nivel2(ID_Nivel2)
);

INSERT INTO Nivel3 (ID_Nivel3, Nombre_Nivel3, ID_Nivel2) VALUES
-- Comercio
(1, 'Centros comerciales', 1),
(2, 'Cadenas y supermercados', 1),
(3, 'Comercio local', 1),

-- Hostelería
(4, 'Restauración', 2),
(5, 'Alojamientos', 2),

-- Histórico y cultural
(6, 'Arqueología', 3),
(7, 'Arte y museos', 3),
(8, 'Arquitectura civil', 3),
(9, 'Monumentos históricos', 3),
(10, 'Teatros y espacios culturales', 3),

-- Urbanismo
(11, 'Movilidad', 4),
(12, 'Infraestructura pública', 4),
(13, 'Organismos públicos', 4),

-- Naturaleza Hydromo
(14, 'Naturaleza - Agua', 5),

-- Naturaleza Phytomo
(15, 'Naturaleza - Tierra', 6);

-- Nivel 4
CREATE TABLE Nivel4 (
    ID_Nivel4 INT PRIMARY KEY,
    Nombre_Nivel4 VARCHAR(150) NOT NULL,
    ID_Nivel3 INT NOT NULL,
    FOREIGN KEY (ID_Nivel3) REFERENCES Nivel3(ID_Nivel3)
);

INSERT INTO Nivel4 (ID_Nivel4, Nombre_Nivel4, ID_Nivel3) VALUES
-- Centros comerciales
(1, 'Bienes', 1),

-- Cadenas y supermercados
(2, 'Bienes', 2),

-- Comercio local
(3, 'Servicios', 3),
(4, 'Bienes', 3),

-- Restauración
(5, 'Servicios', 4),
(6, 'Restauración', 4),

-- Alojamientos
(7, 'Hostales', 5),
(8, 'Casas de huéspedes', 5),
(9, 'Camping', 5),
(10, 'Apartamentos', 5),
(11, 'Hoteles de 1 estrella', 5),
(12, 'Hoteles de 2 estrellas', 5),
(13, 'Hoteles de 3 estrellas', 5),
(14, 'Hoteles de 4 estrellas', 5),
(15, 'Hoteles de 5 estrellas', 5),

-- Arqueología
(16, 'Yacimiento', 6),

-- Arte y museos
(17, 'Museo arqueológico', 7),

-- Monumentos históricos
(18, 'Monasterio', 9),
(19, 'Estatua', 9),
(20, 'Castillo', 9),
(21, 'Catedral', 9),

-- Teatros y espacios culturales
(22, 'Teatro', 10),
(23, 'Cine', 10),

-- Movilidad
(24, 'Estaciones de transporte', 11),
(25, 'Servicio de taxi', 11),

-- Organismos públicos
(26, 'Universidades', 13),
(27, 'Hospitales', 13),

-- Naturaleza - Agua
(28, 'Vivero', 14),
(29, 'Río', 14),
(30, 'Playa fluvial', 14),
(31, 'Pantano', 14),

-- Naturaleza - Tierra
(32, 'Mirador', 15),
(33, 'Parques y jardines', 15),
(34, 'Rutas de senderismo', 15);

-- Nivel 5
CREATE TABLE Nivel5 (
    ID_Nivel5 INT PRIMARY KEY,
    Nombre_Nivel5 VARCHAR(150) NOT NULL,
    ID_Nivel4 INT NOT NULL,
    FOREIGN KEY (ID_Nivel4) REFERENCES Nivel4(ID_Nivel4)
);

INSERT INTO Nivel5 (ID_Nivel5, Nombre_Nivel5, ID_Nivel4) VALUES
-- Estaciones de transporte
(1, 'Estación de tren', 24),
(2, 'Estación de autobuses', 24),

-- Comercio local -> Bienes
(3, 'Panadería', 4),
(4, 'Carnicería', 4),

-- Restauración
(5, 'Restaurantes', 6),
(6, 'Bares', 6),

-- Naturaleza - Agua
(7, 'Cascada', 29);

-- Nivel 6
CREATE TABLE Nivel6 (
    ID_Nivel6 INT PRIMARY KEY,
    Nombre_Nivel6 VARCHAR(150) NOT NULL,
    ID_Nivel5 INT NOT NULL,
    FOREIGN KEY (ID_Nivel5) REFERENCES Nivel5(ID_Nivel5)
);

INSERT INTO Nivel6 (ID_Nivel6, Nombre_Nivel6, ID_Nivel5) VALUES
-- Bares
(1, 'Cervecería', 5),
(2, 'Bar de tapas', 5);
