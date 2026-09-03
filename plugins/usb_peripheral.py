"""USB peripheral management plugin."""

import os
import subprocess
from typing import Any

from ._template import PLUGIN_DESCRIPTION, PLUGIN_NAME, PLUGIN_VERSION


class USBPeripheral:
    """USB device, serial, and peripheral management."""

    def list_devices(self) -> dict[str, Any]:
        """List USB devices via lsusb."""
        try:
            result = subprocess.run(["lsusb"], capture_output=True, text=True, check=True, timeout=10)
            devices = []
            for line in result.stdout.strip().splitlines():
                parts = line.split()
                if len(parts) >= 6:
                    devices.append({
                        "bus": parts[1].rstrip(":"),
                        "device": parts[3].rstrip(":"),
                        "id": parts[5],
                        "name": " ".join(parts[6:]) if len(parts) > 6 else "",
                    })
            return {"status": "success", "count": len(devices), "devices": devices}
        except FileNotFoundError:
            return {"status": "error", "message": "lsusb not installed"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def list_serial_ports(self) -> dict[str, Any]:
        """List available serial ports."""
        ports = []
        for prefix in ["/dev/ttyUSB", "/dev/ttyACM", "/dev/ttyS"]:
            for dev in os.listdir("/dev"):
                if dev.startswith(prefix[len("/dev/"):]):
                    ports.append(os.path.join("/dev", dev))
        return {"status": "success", "ports": sorted(ports)}

    def connect_arduino(self, port: str, baud: int = 9600) -> dict[str, Any]:
        """Connect to Arduino via pyserial."""
        try:
            import serial
            ser = serial.Serial(port=port, baudrate=baud, timeout=2)
            return {"status": "success", "port": port, "baud": baud, "is_open": ser.is_open}
        except ImportError:
            return {"status": "error", "message": "pyserial not installed"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def send_serial(self, port: str, message: str) -> dict[str, Any]:
        """Send message to serial port and read response."""
        try:
            import serial
            with serial.Serial(port=port, baudrate=9600, timeout=2) as ser:
                ser.write((message + "\n").encode("utf-8"))
                response = ser.readline().decode("utf-8", errors="replace").strip()
                return {"status": "success", "sent": message, "response": response}
        except ImportError:
            return {"status": "error", "message": "pyserial not installed"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def mount_usb(self, device: str, mount_point: str) -> dict[str, Any]:
        """Mount a USB device."""
        os.makedirs(mount_point, exist_ok=True)
        try:
            result = subprocess.run(
                ["sudo", "mount", device, mount_point],
                capture_output=True, text=True, timeout=15, check=False,
            )
            return {"status": "success" if result.returncode == 0 else "error", "stdout": result.stdout, "stderr": result.stderr}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def unmount_usb(self, mount_point: str) -> dict[str, Any]:
        """Unmount a USB mount point."""
        try:
            result = subprocess.run(
                ["sudo", "umount", mount_point],
                capture_output=True, text=True, timeout=15, check=False,
            )
            return {"status": "success" if result.returncode == 0 else "error", "stdout": result.stdout, "stderr": result.stderr}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def eject_usb(self, device: str) -> dict[str, Any]:
        """Eject a USB device."""
        try:
            result = subprocess.run(
                ["sudo", "eject", device],
                capture_output=True, text=True, timeout=15, check=False,
            )
            return {"status": "success" if result.returncode == 0 else "error", "stdout": result.stdout, "stderr": result.stderr}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_block_devices(self) -> dict[str, Any]:
        """List block devices via lsblk."""
        try:
            result = subprocess.run(
                ["lsblk", "-J", "-o", "NAME,SIZE,TYPE,MOUNTPOINT,FSTYPE"],
                capture_output=True, text=True, timeout=10, check=True,
            )
            data = json.loads(result.stdout)
            return {"status": "success", "devices": data.get("blockdevices", [])}
        except FileNotFoundError:
            return {"status": "error", "message": "lsblk not installed"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


def get_tools() -> list[dict]:
    return [
        {"name": "list_devices", "description": "List USB devices via lsusb."},
        {"name": "list_serial_ports", "description": "List serial ports."},
        {"name": "connect_arduino", "description": "Connect to Arduino.", "parameters": {"type": "object", "properties": {"port": {"type": "string"}, "baud": {"type": "integer"}}, "required": ["port"]}},
        {"name": "send_serial", "description": "Send serial message.", "parameters": {"type": "object", "properties": {"port": {"type": "string"}, "message": {"type": "string"}}, "required": ["port", "message"]}},
        {"name": "mount_usb", "description": "Mount USB device.", "parameters": {"type": "object", "properties": {"device": {"type": "string"}, "mount_point": {"type": "string"}}, "required": ["device", "mount_point"]}},
        {"name": "unmount_usb", "description": "Unmount USB device.", "parameters": {"type": "object", "properties": {"mount_point": {"type": "string"}}, "required": ["mount_point"]}},
        {"name": "eject_usb", "description": "Eject USB device.", "parameters": {"type": "object", "properties": {"device": {"type": "string"}}, "required": ["device"]}},
        {"name": "get_block_devices", "description": "List block devices."},
    ]


def execute(tool_name: str, params: dict) -> dict:
    instance = USBPeripheral()
    method = getattr(instance, tool_name, None)
    if method and callable(method):
        try:
            return method(**params)
        except TypeError as e:
            return {"status": "error", "message": str(e)}
    return {"status": "error", "error": f"Unknown tool: {tool_name}"}


if __name__ == "__main__":
    print(json.dumps(execute("list_devices", {}), indent=2))
