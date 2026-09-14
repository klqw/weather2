DROP TABLE IF EXISTS weather_observations;

CREATE TABLE weather_observations (
  observation_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  location_id INTEGER NOT NULL,
  observed_date DATE NOT NULL,
  avg_temp DOUBLE PRECISION,
  max_temp DOUBLE PRECISION,
  min_temp DOUBLE PRECISION,
  avg_humidity DOUBLE PRECISION,
  sunshine_hours DOUBLE PRECISION,
  avg_wind_speed DOUBLE PRECISION,
  precipitation DOUBLE PRECISION,
  max_snow_depth DOUBLE PRECISION,

  UNIQUE (location_id, observed_date)
);