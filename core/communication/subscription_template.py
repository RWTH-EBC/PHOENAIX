subscription_template = {
                "description": "QuantumLeap Subscription",
                "subject": {
                    "entities": [
                        {
                            "id": "ID",
                            "type": "TYPE"
                        }
                    ]
                },
                "notification": {
                    "http": {
                        "url": "http://quantumleap:8668/v2/notify"
                    },
                    "metadata": [
                        "dateCreated",
                        "dateModified",
                        "TimeInstant",
                        "timestamp"
                    ]
                },
                "throttling": 0
            }