import json
import sys
import traceback
from .sam_service import SamService

service = SamService()
for line in sys.stdin:
    try:
        data = json.loads(line)
        result = {'result': service.predict(data['image'], data['prompts'])}
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        result = {'error': str(e)}
    print(json.dumps(result), flush=True)
