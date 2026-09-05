import argparse
import json
from pathlib import Path

from .graph_io import read_mtx_to_adj


def getVal(i, j, n):
    return (i - 1) * n + j


def check(n, adj, val, model):
    positive = {lit for lit in model if lit > 0}

    pos = [-1] * (n + 1)

    for i in range(1, n + 1):
        for j in range(1, n + 1):
            if getVal(i, j, n) in positive:
                pos[i] = j

    for u in range(1, n + 1):
        for v in adj[u]:
            if abs(pos[u] - pos[v]) > val:
                print(
                    f"Không thỏa mãn bandwidth: "
                    f"edge ({u}, {v}), "
                    f"|{pos[u]} - {pos[v]}| > {val}"
                )
                return pos, False

    for i in range(1, n + 1):
        for j in range(i + 1, n + 1):
            if pos[i] == pos[j]:
                print(
                    "Hoán vị lỗi trùng nhãn:",
                    i,
                    j,
                    pos[i],
                )
                return pos, False

    for i in range(1, n + 1):
        if pos[i] == -1:
            print("Lỗi không gán nhãn:", i)
            return pos, False

    return pos, True


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--result",
        required=True,
        help="Đường dẫn tới file JSON kết quả",
    )

    args = parser.parse_args()

    result_path = Path(args.result)

    data = json.loads(
        result_path.read_text(encoding="utf-8")
    )

    if data.get("status") != "OPTIMAL":
        print(
            f"Không kiểm tra model vì status = "
            f"{data.get('status')}"
        )
        return

    model = data.get("model")

    if model is None:
        print("JSON không chứa model")
        return

    instance = data["instance"]
    bandwidth = data["bandwidth"]

    n, m, adj = read_mtx_to_adj(instance)

    pos, valid = check(
        n=n,
        adj=adj,
        val=bandwidth,
        model=model,
    )

    print("Labels:")

    for i in range(1, n + 1):
        print(f"{i}: {pos[i]}")

    if valid:
        print("MODEL VALID")
    else:
        print("MODEL INVALID")


if __name__ == "__main__":
    main()