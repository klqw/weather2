DROP TABLE IF EXISTS locations;

CREATE TABLE locations (
    location_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    station_type VARCHAR(1),
    block_no VARCHAR(10),
    name VARCHAR(50),
    kana VARCHAR(50),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    elevation DOUBLE PRECISION,
    name_en VARCHAR(50),
    prefecture_name VARCHAR(50),
    prefecture_name_en VARCHAR(50),
    start_date DATE,
    end_date DATE,
    complete BOOLEAN DEFAULT FALSE,
    last_observation_update DATE,

    UNIQUE (station_type, block_no)
);
