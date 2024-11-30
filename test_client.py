import grpc
import proxy_pb2
import proxy_pb2_grpc
import time


def run():
    try:
        # Connessione al Proxy Service
        with grpc.insecure_channel('localhost:5005') as proxy_channel:
            proxy_stub = proxy_pb2_grpc.ProxyServiceStub(proxy_channel)

            # Lista di utenti e ticker per test
            utenti = [
                {"email": "user1@example.com", "tickers": ["AAPL", "GOOGL", "AMZN"]},
                {"email": "user2@example.com", "tickers": ["MSFT", "TSLA", "NFLX"]},
                {"email": "user3@example.com", "tickers": ["META", "NVDA", "ADBE"]}
            ]

            # --- AUTH Service Tests ---
            print("\n--- AUTH Service Tests ---")
            for utente in utenti:
                # Registra l'utente
                print(f"\n--- Test: RegisterUser for {utente['email']} ---")
                response = proxy_stub.ForwardRequest(proxy_pb2.ProxyUserRequest(
                    service="auth_service",
                    method="RegisterUser",
                    email=utente["email"],
                    ticker=""
                ))
                print(f"RegisterUser Response: {response.status}")

                # Registra i ticker associati all'utente
                for ticker in utente["tickers"]:
                    print(f"\n--- Test: RegisterTicker for {utente['email']} with ticker {ticker} ---")
                    response = proxy_stub.ForwardRequest(proxy_pb2.ProxyUserRequest(
                        service="auth_service",
                        method="RegisterUser",
                        email=utente["email"],
                        ticker=ticker
                    ))
                    print(f"RegisterTicker Response: {response.status}")

            # Attendi che il DataCollector aggiorni i dati
            print("\nAspetto che il DataCollector aggiorni la tabella stock_data...")
            time.sleep(15)  # Aspetta 10 secondi o più, a seconda dell'intervallo del DataCollector

            # --- Stock Management Service Tests ---
            print("\n--- Stock Management Service Tests ---")
            for utente in utenti:
                for ticker in utente["tickers"]:
                    print(f"\n--- Test: GetStock for {utente['email']} and ticker {ticker} ---")
                    response = proxy_stub.ForwardRequest(proxy_pb2.ProxyUserRequest(
                        service="stock_service",
                        method="GetStock",
                        email=utente["email"],
                        ticker=ticker
                    ))
                    if response.status == "Stock found":
                        print(f"GetStock Response: Status={response.status}, Value={response.value}")
                    else:
                        print(f"GetStock Response: Status={response.status}")

                for ticker in utente["tickers"]:
                    print(f"\n--- Test: GetAverage for ticker {ticker} of user {utente['email']} ---")
                    response = proxy_stub.ForwardRequest(proxy_pb2.ProxyUserRequest(
                        service="stock_service",
                        method="GetAverage",
                        email=utente["email"],
                        ticker=ticker,
                        count=5
                    ))
                    if response.status == "Average calculated":
                        print(f"GetAverage Response: Status={response.status}, Average={response.average}")
                    else:
                        print(f"GetAverage Response: Status={response.status}")

            # Test: Cancella un utente
            print("\n--- AUTH Service Cleanup ---")
            for utente in utenti:
                print(f"\n--- Test: DeleteUser for {utente['email']} ---")
                response = proxy_stub.ForwardRequest(proxy_pb2.ProxyUserRequest(
                    service="auth_service",
                    method="DeleteUser",
                    email=utente["email"]
                ))
                print(f"DeleteUser Response: {response.status}")

    except grpc.RpcError as e:
        print(f"Errore gRPC: {e.code()} - {e.details()}")


if __name__ == "__main__":
    run()