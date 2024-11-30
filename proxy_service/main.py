from concurrent import futures
import grpc
import proxy_pb2
import proxy_pb2_grpc

# Import per connettersi agli altri servizi
import auth_pb2
import auth_pb2_grpc
import stock_pb2
import stock_pb2_grpc

# Configurazione Redis per la politica "At Most Once"
import redis

redis_client = redis.StrictRedis(host='redis', port=6379, db=0)

# Funzione per gestire richieste duplicate
def is_duplicate_request(request_id):
    if redis_client.get(request_id):
        return True  # La richiesta è duplicata
    redis_client.setex(request_id, 300, "processed")  # TTL di 5 minuti
    return False

class ProxyService(proxy_pb2_grpc.ProxyServiceServicer):
    def ForwardRequest(self, request, context):
        # Genera un identificativo unico per la richiesta, ora con email e ticker
        request_id = f"{request.service}:{request.method}:{request.email}:{request.ticker}"

        # Verifica richieste duplicate
        if is_duplicate_request(request_id):
            return proxy_pb2.ProxyUserResponse(status="Duplicate request - Already processed")

        # Inoltra la richiesta al microservizio appropriato
        if request.service == "auth_service":
            return self.handle_auth_service(request, context)
        elif request.service == "stock_service":
            return self.handle_stock_service(request, context)
        else:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("Invalid service specified")
            return proxy_pb2.ProxyUserResponse(status="Invalid service")

    def handle_auth_service(self, request, context):
        """
        Gestisce le richieste verso AUTH Service.
        """
        with grpc.insecure_channel('auth_service:5001') as channel:
            stub = auth_pb2_grpc.AuthServiceStub(channel)
            if request.method == "RegisterUser":
                response = stub.RegisterUser(auth_pb2.AuthUserRequest(
                    email=request.email,
                    ticker=request.ticker
                ))
            elif request.method == "UpdateUser":
                response = stub.UpdateUser(auth_pb2.AuthUserRequest(
                    email=request.email,
                    ticker=request.ticker
                ))
            elif request.method == "DeleteUser":
                response = stub.DeleteUser(auth_pb2.AuthUserRequest(
                    email=request.email
                ))
            else:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details("Invalid method for auth_service")
                return proxy_pb2.ProxyUserResponse(status="Invalid method")
            return proxy_pb2.ProxyUserResponse(status=response.status)

    def handle_stock_service(self, request, context):
        """
        Gestisce le richieste verso Stock Management Service.
        """
        with grpc.insecure_channel('stock_service:5002') as channel:
            stub = stock_pb2_grpc.StockServiceStub(channel)
            if request.method == "GetStock":
                # Includi l'email nel messaggio di richiesta per il controllo del ticker associato all'utente
                response = stub.GetStock(stock_pb2.StockQuery(
                    email=request.email,
                    ticker=request.ticker
                ))
                return proxy_pb2.ProxyUserResponse(
                    status=response.status,
                    value=response.value
                )
            elif request.method == "GetAverage":
                # Includi l'email nel messaggio di richiesta per il controllo del ticker associato all'utente
                response = stub.GetAverage(stock_pb2.AverageQuery(
                    email=request.email,
                    ticker=request.ticker,
                    count=request.count
                ))
                return proxy_pb2.ProxyUserResponse(
                    status=response.status,
                    average=response.average
                )
            else:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details("Invalid method for stock_service")
                return proxy_pb2.ProxyUserResponse(status="Invalid method")

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    proxy_pb2_grpc.add_ProxyServiceServicer_to_server(ProxyService(), server)
    server.add_insecure_port('0.0.0.0:5005')
    server.start()
    print("Proxy Service running on port 5005")
    server.wait_for_termination()

if __name__ == '__main__':
    serve()