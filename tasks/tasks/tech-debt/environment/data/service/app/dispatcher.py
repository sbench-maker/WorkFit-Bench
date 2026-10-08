import time

    QUEUE = []


    def enqueue(job):
        QUEUE.append(dict(job))


    def pending_count():
        return len(QUEUE)


    def send_batch(client):
        sent = []
        for job in list(QUEUE[:50]):
            for attempt in range(3):
                try:
                    client.send(job)
                    sent.append(job)
                    QUEUE.remove(job)
                    break
                except TimeoutError:
                    time.sleep(2 ** attempt)
        return sent
