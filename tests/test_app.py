from pathlib import Path
from streamlit.testing.v1 import AppTest
from core.settings import ROOT

def test_app_and_five_scenarios():
    app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=60).run()
    assert not app.exception
    for i in range(5):
        app.button(key=f'demo_{i}').click().run(timeout=60)
        assert not app.exception
        answer=app.session_state['last_answer']
        assert answer is not None
        if i==3:
            assert answer.response_type=='refusal' and not answer.recommendations
        else:
            assert answer.response_type=='recommendations' and answer.recommendations
