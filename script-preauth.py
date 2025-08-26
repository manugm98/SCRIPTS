#!/usr/bin/env python3
import asyncio, time, uuid, statistics
import httpx

URL = "https://api-uat.kushkipagos.com/subscriptions/v1/card/1756247760977978/authorize"
PRIVATE_MERCHANT_ID = "77e6c728052745a7862f5d0a230ea4e1"

PAYLOAD = {
    "amount": {"ice": 0, "iva": 0, "subtotalIva": 0, "subtotalIva0": 600, "currency": "MXN"},
    "name": "John",
    "lastName": "Doe",
    "email": "user@example.com",
    "fullResponse": "v2"
}

TOTAL = 100        # total de peticiones
CONCURRENCY = 100  # cuántas al mismo tiempo
TIMEOUT = 15       # seg
MAX_CONNECTIONS = 200
MAX_KEEPALIVE = 50

def pct(vals, p):
    if not vals: return 0.0
    s = sorted(vals)
    k = int(round((p/100.0)*(len(s)-1)))
    k = max(0, min(k, len(s)-1))
    return s[k]

async def worker(sema: asyncio.Semaphore, client: httpx.AsyncClient, idx: int, lat_ms, codes, errors):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Private-Merchant-Id": PRIVATE_MERCHANT_ID,
        "Idempotency-Key": str(uuid.uuid4())
    }
    async with sema:
        t0 = time.perf_counter()
        try:
            r = await client.post(URL, headers=headers, json=PAYLOAD, timeout=TIMEOUT)
            dt = (time.perf_counter() - t0) * 1000.0
            lat_ms.append(dt)
            codes.append(r.status_code)
            # 👉 imprimir cada resultado
            print(f"[{idx+1}/{TOTAL}] HTTP {r.status_code} | {dt:.1f} ms")
        except Exception as e:
            dt = (time.perf_counter() - t0) * 1000.0
            lat_ms.append(dt)
            errors.append(str(e))
            print(f"[{idx+1}/{TOTAL}] ERROR | {dt:.1f} ms | {e}")

async def main():
    try:
        import uvloop
        uvloop.install()
    except Exception:
        pass

    limits = httpx.Limits(max_connections=MAX_CONNECTIONS,
                          max_keepalive_connections=MAX_KEEPALIVE)
    async with httpx.AsyncClient(http2=True, limits=limits) as client:
        sema = asyncio.Semaphore(CONCURRENCY)
        lat_ms, codes, errors = [], [], []
        start = time.perf_counter()

        tasks = [asyncio.create_task(worker(sema, client, i, lat_ms, codes, errors))
                 for i in range(TOTAL)]
        await asyncio.gather(*tasks)

        dur = time.perf_counter() - start

    # --- Resumen ---
    by_code = {}
    for c in codes:
        by_code[c] = by_code.get(c, 0) + 1
    ok2xx = sum(1 for c in codes if 200 <= c < 300)

    print("\n========= RESUMEN =========")
    print(f"Total solicitadas: {TOTAL}")
    print(f"Exitos 2xx: {ok2xx} | Errores (excepciones): {len(errors)}")
    print("Códigos HTTP:")
    for k in sorted(by_code.keys()):
        print(f"  {k}: {by_code[k]}")

    if lat_ms:
        print("\nLatencias (ms):")
        print(f"  min: {min(lat_ms):.1f}  |  p50: {pct(lat_ms,50):.1f}  |  p90: {pct(lat_ms,90):.1f}  |  p95: {pct(lat_ms,95):.1f}  |  p99: {pct(lat_ms,99):.1f}  |  max: {max(lat_ms):.1f}  |  mean: {statistics.fmean(lat_ms):.1f}")
        print(f"Duración total: {dur:.2f} s")
        print(f"Throughput promedio: {TOTAL/dur:.2f} req/s")
    print("===========================")

if __name__ == "__main__":
    asyncio.run(main())
