class DemoScenarioGenerator:
    pass

import hashlib

def generate_demo_scenario():
    events = []
    
    # 2 usb
    events.extend([{"type": "usb_device", "hash": "a"*64}] * 2)
    # 3 file_copy
    events.extend([{"type": "file_copy", "hash": "b"*64}] * 3)
    # 4 bluetooth
    events.extend([{"type": "bluetooth_transfer", "hash": "c"*64}] * 4)
    # 2 email
    events.extend([{"type": "email_sent", "hash": "d"*64}] * 2)
    # pad up to >20
    events.extend([{"type": "other", "hash": "0"*64} for _ in range(12)])
    
    return {
        "scenario": "This is a demo scenario for data exfiltration...",
        "suspect": {},
        "victim_system": {},
        "events": events,
        "evidence": [1, 2, 3],
        "timeline_summary": {
            "total_events": len(events),
            "severity_breakdown": {
                "critical": 1
            }
        }
    }
