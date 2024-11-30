import os
import time
import grpc
import yfinance as yf
import mysql.connector
from concurrent import futures
from pybreaker import CircuitBreaker
import datacollector_pb2
import datacollector_pb2_grpc

# Configurazione del database
db_config = {
    'host': 'mysql_db',
    'user': 'root',
    'password': 'example',
    'database': 'finance_data',
    'connect_timeout': 10  # Timeout per evitare blocchi prolungati
}

# Configurazione del Circuit Breaker
breaker = CircuitBreaker(fail_max=3, reset_timeout=60)


class DataCollectorService(datacollector_pb2_grpc.DataCollectorServiceServicer):
    def __init__(self):
        self.db_config = db_config

    @breaker
    def get_stock_value(self, ticker):
        """
        Recupera il valore corrente del ticker da Yahoo Finance.
        """
        try:
            stock = yf.Ticker(ticker)
            value = (
                stock.info.get('regularMarketPrice')
                or stock.info.get('previousClose')
                or stock.info.get('ask')
            )
            if value is None:
                data = stock.history(period="1d")
                if not data.empty:
                    value = data['Close'].iloc[-1]
            return value
        except Exception as e:
            print(f"Errore nel recupero dei dati per {ticker}: {e}")
            return None

    def collect_stock_data_internal(self):
        """
        Logica per raccogliere i dati sui ticker registrati e inserirli nel database.
        """
        connection = None
        cursor = None
        collected_count = 0

        try:
            connection = mysql.connector.connect(**self.db_config)
            cursor = connection.cursor()

            # Recupera i ticker dalla tabella user_tickers
            cursor.execute("SELECT DISTINCT ticker FROM user_tickers")
            tickers = [row[0] for row in cursor.fetchall()]
            print(f"Tickers trovati: {tickers}")

            for ticker in tickers:
                try:
                    stock_value = self.get_stock_value(ticker)
                    if stock_value is not None:
                        print(f"Aggiornamento per {ticker}: valore={stock_value}")
                        cursor.execute(
                            """
                            INSERT INTO stock_data (ticker, value)
                            VALUES (%s, %s)
                            ON DUPLICATE KEY UPDATE value = VALUES(value), timestamp = CURRENT_TIMESTAMP
                            """,
                            (ticker, stock_value)
                        )
                        collected_count += 1
                except Exception as e:
                    print(f"Errore durante l'aggiornamento per {ticker}: {e}")

            connection.commit()
            print("Aggiornamento completato.")
        except Exception as e:
            print(f"Errore durante la raccolta dati: {e}")
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

        return collected_count

    def CollectStockData(self, request, context):
        """
        Metodo gRPC per raccogliere i dati sui ticker.
        """
        try:
            collected_count = self.collect_stock_data_internal()
            return datacollector_pb2.CollectionResponse(
                status="Data collection completed successfully",
                collected=collected_count
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return datacollector_pb2.CollectionResponse(
                status="Error during data collection",
                collected=0
            )

    def start_continuous_collection(self, interval=60):
        """
        Avvia un ciclo continuo per raccogliere i dati sui ticker a intervalli regolari.
        """
        print("Attesa per inizializzare il ciclo continuo...")
        time.sleep(10)  # Ritardo iniziale per garantire che il database sia pronto

        while True:
            try:
                print("Avvio della raccolta automatica...")
                self.collect_stock_data_internal()
            except Exception as e:
                print(f"Errore durante la raccolta automatica: {e}")
            finally:
                time.sleep(interval)  # Attendi l'intervallo specificato


def serve():
    """
    Avvia il server gRPC e il ciclo continuo.
    """
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    service = DataCollectorService()

    # Registra il servizio gRPC
    datacollector_pb2_grpc.add_DataCollectorServiceServicer_to_server(service, server)
    server.add_insecure_port('0.0.0.0:5004')

    # Avvia il ciclo continuo in un thread separato
    executor = futures.ThreadPoolExecutor(max_workers=1)
    executor.submit(service.start_continuous_collection, interval=60)

    server.start()
    print("DataCollector Service in esecuzione sulla porta 5004...")
    server.wait_for_termination()


if __name__ == '__main__':
    serve()