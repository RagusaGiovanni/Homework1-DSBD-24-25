from concurrent import futures
import grpc
import mysql.connector
import auth_pb2
import auth_pb2_grpc

# Configurazione del database
db_config = {
    'host': 'mysql_db',
    'user': 'root',
    'password': 'example',
    'database': 'finance_data'
}


class AuthService(auth_pb2_grpc.AuthServiceServicer):
    def __init__(self):
        self.db_config = db_config

    def RegisterUser(self, request, context):
        """
        Registra un nuovo utente o associa un ticker esistente a un utente registrato.
        """
        connection = mysql.connector.connect(**self.db_config)
        cursor = connection.cursor()
        try:
            # Controlla se l'utente esiste
            cursor.execute("SELECT id FROM users WHERE email = %s", (request.email,))
            user = cursor.fetchone()

            if user is None:
                # Registra un nuovo utente
                cursor.execute("INSERT INTO users (email) VALUES (%s)", (request.email,))
                connection.commit()
                user_id = cursor.lastrowid
                print(f"Utente {request.email} registrato con ID {user_id}")
            else:
                user_id = user[0]

            # Aggiungi un ticker per l'utente
            if request.ticker:
                cursor.execute(
                    "SELECT id FROM user_tickers WHERE user_id = %s AND ticker = %s",
                    (user_id, request.ticker)
                )
                existing_ticker = cursor.fetchone()

                if existing_ticker:
                    return auth_pb2.AuthUserResponse(status="Ticker already registered for user")
                else:
                    cursor.execute(
                        "INSERT INTO user_tickers (user_id, ticker) VALUES (%s, %s)",
                        (user_id, request.ticker)
                    )
                    connection.commit()
                    print(f"Ticker {request.ticker} registrato per l'utente {request.email}")

            return auth_pb2.AuthUserResponse(status="User and ticker registered successfully")

        except mysql.connector.Error as e:
            print(f"Errore nel database: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details("Database error")
            return auth_pb2.AuthUserResponse(status="Error during registration")

        finally:
            cursor.close()
            connection.close()

    def UpdateUser(self, request, context):
        """
        Aggiorna il ticker associato a un utente esistente.
        """
        connection = mysql.connector.connect(**self.db_config)
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT id FROM users WHERE email = %s", (request.email,))
            user = cursor.fetchone()

            if user is None:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("User not found")
                return auth_pb2.AuthUserResponse(status="User not found")

            user_id = user[0]

            # Aggiorna il ticker per l'utente
            cursor.execute(
                "UPDATE user_tickers SET ticker = %s WHERE user_id = %s AND ticker = %s",
                (request.ticker, user_id, request.ticker)
            )
            connection.commit()

            if cursor.rowcount == 0:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("Ticker not found for user")
                return auth_pb2.AuthUserResponse(status="Ticker not found for user")

            return auth_pb2.AuthUserResponse(status="User ticker updated successfully")

        except mysql.connector.Error as e:
            print(f"Errore nel database: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details("Database error")
            return auth_pb2.AuthUserResponse(status="Error during update")

        finally:
            cursor.close()
            connection.close()

    def DeleteUser(self, request, context):
        """
        Cancella un utente o un ticker associato all'utente.
        """
        connection = mysql.connector.connect(**self.db_config)
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT id FROM users WHERE email = %s", (request.email,))
            user = cursor.fetchone()

            if user is None:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("User not found")
                return auth_pb2.AuthUserResponse(status="User not found")

            user_id = user[0]

            if request.ticker:
                # Cancella solo il ticker specificato
                cursor.execute(
                    "DELETE FROM user_tickers WHERE user_id = %s AND ticker = %s",
                    (user_id, request.ticker)
                )
                connection.commit()

                if cursor.rowcount == 0:
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    context.set_details("Ticker not found for user")
                    return auth_pb2.AuthUserResponse(status="Ticker not found for user")

                return auth_pb2.AuthUserResponse(status="Ticker deleted successfully")

            else:
                # Cancella l'utente e tutti i suoi ticker
                cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
                connection.commit()
                return auth_pb2.AuthUserResponse(status="User and all tickers deleted successfully")

        except mysql.connector.Error as e:
            print(f"Errore nel database: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details("Database error")
            return auth_pb2.AuthUserResponse(status="Error during deletion")

        finally:
            cursor.close()
            connection.close()


def serve():
    """
    Avvia il server gRPC per gestire le richieste di autenticazione.
    """
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    auth_pb2_grpc.add_AuthServiceServicer_to_server(AuthService(), server)
    server.add_insecure_port('0.0.0.0:5001')
    server.start()
    print("AUTH Service in esecuzione sulla porta 5001...")
    server.wait_for_termination()


if __name__ == '__main__':
    serve()