from .client import GraphClient


def main():
    client = GraphClient(graph_name="weave_test")

    if not client.health_check():
        raise RuntimeError("FalkorDB health check failed")

    result = client.execute("RETURN 1 AS ok")

    print("Health check: PASS")
    print("Query result:", result.result_set)


if __name__ == "__main__":
    main()
