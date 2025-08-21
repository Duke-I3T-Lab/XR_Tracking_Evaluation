import asyncio
import websockets
import os
from datetime import datetime

UPLOAD_DIR = "device_trajectory_logs"

async def handle_client(websocket):
    file_data = bytearray()
    try:
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        
        # Generate filename upfront
        timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        filename = f"AppleVisionPro_{timestamp}.csv"
        filepath = os.path.join(UPLOAD_DIR, filename)
        
        # Receive chunks until connection closes
        async for message in websocket:
            if isinstance(message, bytes):
                file_data.extend(message)
                print(f"Received chunk: {len(message)} bytes")
            elif message == "EOF":
                break  # Client signals end of transmission
        
        # Save file after receiving all chunks
        if file_data:
            with open(filepath, "wb") as f:
                f.write(file_data)
            print(f"Saved {len(file_data)} bytes to {filename}")
            
        # Acknowledge successful reception
        await websocket.send("File received successfully")
        
    except Exception as e:
        print(f"Error handling client: {e}")
        await websocket.send(f"Error: {str(e)}")
    finally:
        # Properly close connection with status code 1000 (Normal Closure)
        await websocket.close(code=1000)

async def main(host, port):
    # Increased max_size to 100MB and added ping settings
    async with websockets.serve(
        handle_client,
        host,
        port,
        max_size=100 * 1024 * 1024,  # 100MB
        ping_interval=20,
        ping_timeout=20
    ):
        print(f"Server started at ws://{host}:{port}")
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="192.168.0.108", help="Host address")
    parser.add_argument("--port", type=int, default=8765, help="Port number")
    args = parser.parse_args()
    
    asyncio.run(main(args.host, args.port))
