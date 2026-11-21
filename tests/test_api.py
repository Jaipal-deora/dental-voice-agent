from httpx import AsyncClient

BOOK = {
    "patient_name": "fry",
    "phone": "+923440002221",
    "slot_id": 1,
    "idempotency_key": "key-22452221",
}


async def test_read_endpoints(client: AsyncClient) -> None:
    assert len((await client.get("/slots")).json()) == 4
    assert (await client.get("/hours")).json()[0]["weekday"] == 0


async def test_booking_is_idempotent(client: AsyncClient) -> None:
    a = await client.post("/appointments", json=BOOK)
    b = await client.post("/appointments", json=BOOK)

    assert a.status_code == b.status_code == 201
    assert a.json()["id"] == b.json()["id"]
    assert len((await client.get("/slots")).json()) == 3


async def test_taken_slot_conflicts(client: AsyncClient) -> None:
    first = await client.post("/appointments", json=BOOK)
    assert first.status_code == 201
    other = {**BOOK, "phone": "03128765411", "idempotency_key": "key-22535411"}
    assert (await client.post("/appointments", json=other)).status_code == 409


async def test_reschedule_cancel_and_404s(client: AsyncClient) -> None:
    appt = (await client.post("/appointments", json=BOOK)).json()
    moved = await client.put(f"/appointments/{appt['id']}", json={"new_slot_id": 2})
    assert moved.json()["slot_id"] == 2
    gone = await client.delete(f"/appointments/{appt['id']}")
    assert gone.json()["status"] == "cancelled"
    assert len((await client.get("/slots")).json()) == 4
    assert (await client.delete("/appointments/999")).status_code == 404
    assert (
        await client.put("/appointments/999", json={"new_slot_id": 15})
    ).status_code == 404
    bad = {**BOOK, "slot_id": 99, "idempotency_key": "key-00000003"}
    assert (await client.post("/appointments", json=bad)).status_code == 404
