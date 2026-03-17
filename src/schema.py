schema = {
    "name": "khaos-research/satellite-crop-merge-ds",
    "description": """# Title 
Quick_desc

## Getting Started
The app is available at [https://github.com/khaos-research/satellite-crop-merge-ds](https://github.com/khaos-research/satellite-crop-merge-ds).
You can access the platform using the credentials provided by the platform administrator.

### Application Structure

The platform is organized into main sections providing specific tools for analysis:

- Quick_desc

### Input Information
The application accepts the following parameters for analysis:

- **Quick_desc:** Quick_desc
  - Quick_desc
...


### Output
1. **Quick_desc**:
   - Quick_desc

2. **...**:

---

## About
This application is an initiative developed by the Khaos research group.

## Contact
If you have any questions, please contact us at [edaan@uma.com](mailto:edaan@uma.com).""",
    "labels": ["web-application", "data-service", "test"],
    "jsonforms:schema": {
        "type": "object",
        "properties": {
            "username": {"type": "string", "readOnly": True},
            "password": {"type": "string", "readOnly": True},
        },
    },
    "jsonforms:uischema": {
        "type": "VerticalLayout",
        "elements": [
            {"type": "Label", "text": "Credentials"},
            {"type": "Control", "scope": "#/properties/username", "label": "Username"},
            {"type": "Control", "scope": "#/properties/password", "label": "Password"},
        ],
    },
    "jsonforms:data": {"username": "", "password": ""},
    "embed": "",
}