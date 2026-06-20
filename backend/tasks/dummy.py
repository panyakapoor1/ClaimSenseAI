import asyncio

async def dummy_task(ctx, task_name: str, delay_seconds: int = 5):
    """
    A dummy task to simulate a long-running AI operation.
    """
    print(f"Starting task: {task_name}...")
    await asyncio.sleep(delay_seconds)
    print(f"Finished task: {task_name}.")
    return {"status": "success", "task": task_name}
