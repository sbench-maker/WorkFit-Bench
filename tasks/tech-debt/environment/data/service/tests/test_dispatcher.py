import random
    import time
    from app.dispatcher import QUEUE, enqueue, send_batch


    class Client:
        def send(self, job):
            time.sleep(random.random() / 100)
            if random.random() < 0.08:
                raise TimeoutError()


    def test_batch_eventually_empties_queue():
        QUEUE.clear()
        enqueue({"order_id": 1})
        send_batch(Client())
        assert not QUEUE
