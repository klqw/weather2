-- daily_avg
DROP TABLE IF EXISTS daily_avg_stats;

CREATE TABLE daily_avg_stats (
  location_id INTEGER NOT NULL,
  month SMALLINT NOT NULL,
  day SMALLINT NOT NULL,
  avg_temp DOUBLE PRECISION,
  max_temp DOUBLE PRECISION,
  min_temp DOUBLE PRECISION,
  avg_humidity DOUBLE PRECISION,
  sunshine_hours DOUBLE PRECISION,
  avg_wind_speed DOUBLE PRECISION,
  precipitation DOUBLE PRECISION,
  max_snow_depth DOUBLE PRECISION,

  PRIMARY KEY (location_id, month, day),

  CHECK (month BETWEEN 1 AND 12),
  CHECK (day BETWEEN 1 AND 31)
);

-- month_avg
DROP TABLE IF EXISTS month_avg_stats;

CREATE TABLE month_avg_stats (
  location_id INTEGER NOT NULL,
  month SMALLINT NOT NULL,
  avg_temp DOUBLE PRECISION,
  max_temp DOUBLE PRECISION,
  min_temp DOUBLE PRECISION,
  avg_humidity DOUBLE PRECISION,
  sunshine_hours DOUBLE PRECISION,
  avg_wind_speed DOUBLE PRECISION,
  precipitation DOUBLE PRECISION,
  max_snow_depth DOUBLE PRECISION,

  PRIMARY KEY (location_id, month),

  CHECK (month BETWEEN 1 AND 12)
);

-- overall_avg
DROP TABLE IF EXISTS overall_avg_stats;

CREATE TABLE overall_avg_stats (
  location_id INTEGER PRIMARY KEY,
  avg_temp DOUBLE PRECISION,
  max_temp DOUBLE PRECISION,
  min_temp DOUBLE PRECISION,
  avg_humidity DOUBLE PRECISION,
  sunshine_hours DOUBLE PRECISION,
  avg_wind_speed DOUBLE PRECISION,
  precipitation DOUBLE PRECISION,
  max_snow_depth DOUBLE PRECISION
);

-- daily_max
DROP TABLE IF EXISTS daily_max_stats;

CREATE TABLE daily_max_stats (
  location_id INTEGER NOT NULL,
  month SMALLINT NOT NULL,
  day SMALLINT NOT NULL,
  avg_temp DOUBLE PRECISION,
  max_temp DOUBLE PRECISION,
  min_temp DOUBLE PRECISION,
  avg_humidity DOUBLE PRECISION,
  sunshine_hours DOUBLE PRECISION,
  avg_wind_speed DOUBLE PRECISION,
  precipitation DOUBLE PRECISION,
  max_snow_depth DOUBLE PRECISION,

  PRIMARY KEY (location_id, month, day),

  CHECK (month BETWEEN 1 AND 12),
  CHECK (day BETWEEN 1 AND 31)
);

-- daily_min
DROP TABLE IF EXISTS daily_min_stats;

CREATE TABLE daily_min_stats (
  location_id INTEGER NOT NULL,
  month SMALLINT NOT NULL,
  day SMALLINT NOT NULL,
  avg_temp DOUBLE PRECISION,
  max_temp DOUBLE PRECISION,
  min_temp DOUBLE PRECISION,
  avg_humidity DOUBLE PRECISION,
  sunshine_hours DOUBLE PRECISION,
  avg_wind_speed DOUBLE PRECISION,
  precipitation DOUBLE PRECISION,
  max_snow_depth DOUBLE PRECISION,

  PRIMARY KEY (location_id, month, day),

  CHECK (month BETWEEN 1 AND 12),
  CHECK (day BETWEEN 1 AND 31)
);
