# Requests Documentation

## Overview
Requests is a simple, yet elegant HTTP library for Python. It allows you to send HTTP/1.1 requests extremely easily and provides a clean, Pythonic API for accessing web resources.

## Installation
```bash
pip install requests
```

## Key Features
- Keep-Alive & Connection Pooling
- International Domains and URLs
- Sessions with Cookie Persistence
- Browser-style SSL Verification
- Basic/Digest Authentication
- Elegant Key/Value Cookies
- Automatic Decompression
- Automatic Content Decoding
- Unicode Response Bodies
- Multipart File Uploads
- HTTP(S) Proxy Support
- Connection Timeouts
- Streaming Downloads
- Chunked Requests
- .netrc Support

## Basic Usage

### Making a Simple Request
```python
import requests

# GET request
response = requests.get('https://api.github.com/user', auth=('user', 'pass'))
print(response.status_code)  # 200
print(response.headers['content-type'])  # 'application/json; charset=utf8'
print(response.json())  # JSON response content

# POST request
response = requests.post('https://httpbin.org/post', data={'key': 'value'})

# Other HTTP methods
requests.put('https://httpbin.org/put', data={'key': 'value'})
requests.delete('https://httpbin.org/delete')
requests.head('https://httpbin.org/get')
requests.options('https://httpbin.org/get')
```

### Working with Response Objects
```python
response = requests.get('https://api.github.com/user', auth=('user', 'pass'))

# Response content
response.text  # Text content
response.content  # Binary content
response.json()  # JSON content

# Response metadata
response.status_code  # HTTP status code
response.headers  # Response headers
response.cookies  # Response cookies
response.url  # Final URL location
response.history  # Redirection history
```

## Current Version
Version: 2.32.3 (latest as of documentation creation)

## Dependencies
- charset-normalizer (>=2,<4)
- idna (>=2.5,<4)
- urllib3 (>=1.21.1,<3)
- certifi (>=2017.4.17)

## Resources
- [Official Documentation](https://requests.readthedocs.io)
- [GitHub Repository](https://github.com/psf/requests)
- [PyPI Project Page](https://pypi.org/project/requests/)

## License
Requests is released under the Apache 2.0 license. 