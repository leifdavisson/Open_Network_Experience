import test from "node:test";
import assert from "node:assert";
import { offlineStorage } from "../src/db/indexed_db.js";

test("Offline Storage - Enqueue and Peek batch with fallback memory queue", async () => {
  await offlineStorage.clear();

  const countInitial = await offlineStorage.count();
  assert.strictEqual(countInitial, 0);

  // Enqueue 3 items
  await offlineStorage.enqueue({ event: "telemetry-1", ping: 15 });
  await offlineStorage.enqueue({ event: "telemetry-2", ping: 22 });
  await offlineStorage.enqueue({ event: "telemetry-3", ping: 30 });

  const countAfter = await offlineStorage.count();
  assert.strictEqual(countAfter, 3);

  // Peek batch of 2
  const batch = await offlineStorage.peekBatch(2);
  assert.strictEqual(batch.length, 2);
  assert.strictEqual(batch[0].payload.event, "telemetry-1");
  assert.strictEqual(batch[1].payload.event, "telemetry-2");

  // Delete first item
  await offlineStorage.deleteBatch([batch[0].id]);
  const countRemaining = await offlineStorage.count();
  assert.strictEqual(countRemaining, 2);

  // Clear
  await offlineStorage.clear();
  assert.strictEqual(await offlineStorage.count(), 0);
});

test("Offline Storage - FIFO backpressure eviction at max records", async () => {
  await offlineStorage.clear();
  const maxCap = 5;

  for (let i = 1; i <= 8; i++) {
    await offlineStorage.enqueue({ num: i }, maxCap);
  }

  const count = await offlineStorage.count();
  assert.strictEqual(count, 5);

  const batch = await offlineStorage.peekBatch(10);
  assert.strictEqual(batch.length, 5);
  // Oldest (1, 2, 3) should have been evicted; earliest should be 4
  assert.strictEqual(batch[0].payload.num, 4);
  assert.strictEqual(batch[4].payload.num, 8);

  await offlineStorage.clear();
});
