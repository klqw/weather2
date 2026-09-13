import configparser
import psycopg

def get_connection(config):
  secret_file = config["DATABASE"]["secret_file"]

  secret_config = configparser.ConfigParser()
  secret_config.read(secret_file, encoding="utf-8")

  conn = psycopg.connect(
    host=secret_config["DATABASE"]["host"],
    port=secret_config["DATABASE"]["port"],
    dbname=secret_config["DATABASE"]["dbname"],
    user=secret_config["DATABASE"]["user"],
    password=secret_config["DATABASE"]["password"]
  )

  return conn