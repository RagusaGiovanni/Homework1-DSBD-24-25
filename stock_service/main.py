from concurrent import futures
import grpc
import stock_pb2
import stock_pb2_grpc
import mysql.connector

# Configurazione del database
db_config = {
    'host': 'mysql_db',
    'user': 'root',
    'password': 'example',
    'database': 'finance_data'
}

class StockService(stock_pb2_grpc.StockServiceServicer):
    def GetStock(self, request, context):
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()
        try:
            # Verifica se l'utente ha registrato il ticker
            cursor.execute("SELECT id FROM users WHERE email=%s", (request.email,))
            user = cursor.fetchone()

            if not user:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("User not found")
                return stock_pb2.StockResponse(status="User not found")

            user_id = user[0]
            cursor.execute("SELECT id FROM user_tickers WHERE user_id=%s AND ticker=%s", (user_id, request.ticker))
            ticker_exists = cursor.fetchone()

            if not ticker_exists:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("Ticker not found for this user")
                return stock_pb2.StockResponse(status="Ticker not found for this user")

            # Recupera il valore più recente del ticker
            cursor.execute("SELECT value FROM stock_data WHERE ticker=%s ORDER BY timestamp DESC LIMIT 1", (request.ticker,))
            result = cursor.fetchone()
            if result:
                return stock_pb2.StockResponse(status="Stock found", value=result[0])
            else:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("Stock not found")
                return stock_pb2.StockResponse(status="Stock not found")
        finally:
            cursor.close()
            connection.close()

    def GetAverage(self, request, context):
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()
        try:
            # Verifica se l'utente ha registrato il ticker
            cursor.execute("SELECT id FROM users WHERE email=%s", (request.email,))
            user = cursor.fetchone()

            if not user:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("User not found")
                return stock_pb2.AverageResponse(status="User not found")

            user_id = user[0]
            cursor.execute("SELECT id FROM user_tickers WHERE user_id=%s AND ticker=%s", (user_id, request.ticker))
            ticker_exists = cursor.fetchone()

            if not ticker_exists:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("Ticker not found for this user")
                return stock_pb2.AverageResponse(status="Ticker not found for this user")

            # Calcola la media degli ultimi X valori per il ticker
            cursor.execute("""
                SELECT AVG(value) 
                FROM (SELECT value FROM stock_data WHERE ticker=%s ORDER BY timestamp DESC LIMIT %s) as subquery
            """, (request.ticker, request.count))
            result = cursor.fetchone()
            if result and result[0] is not None:
                return stock_pb2.AverageResponse(status="Average calculated", average=result[0])
            else:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("Stock not found or insufficient data")
                return stock_pb2.AverageResponse(status="Stock not found or insufficient data")
        finally:
            cursor.close()
            connection.close()

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    stock_pb2_grpc.add_StockServiceServicer_to_server(StockService(), server)
    server.add_insecure_port('0.0.0.0:5002')
    server.start()
    print("Stock Service running on port 5002")
    server.wait_for_termination()

if __name__ == '__main__':
    serve()