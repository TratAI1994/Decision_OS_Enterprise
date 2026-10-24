"""Streamlit journey shell. No raw HTML or privileged backend mutation."""
from backend.transformation_journey import INDUSTRIES,FRAMEWORKS,Journey,STEPS

def render(api=None,navigate=None):
 import streamlit as st
 st.title('Transformation Command Center')
 st.caption('Start with an objective. Your existing Decision OS workspaces remain the authoritative systems.')
 a,b=st.columns(2)
 with a: industry=st.selectbox('Industry',list(INDUSTRIES),key='tx_industry')
 with b: framework=st.selectbox('Framework lens',list(FRAMEWORKS),key='tx_framework')
 objective=st.text_input('Business objective',key='tx_objective',placeholder='Reduce manufacturing release-cycle delays')
 if len(objective.strip())<4:
  st.info('Enter a measurable objective to generate a guided plan. Nothing is approved automatically.')
  return
 journey=Journey(industry,framework,objective)
 steps=journey.checklist()
 st.progress(0,text='0 of 8 steps verified — no live completion evidence linked')
 st.warning('Advisory template only. Framework mapping is not provider accreditation or regulatory compliance certification.')
 left,right=st.columns([2,1])
 with left:
  step=st.selectbox('Workflow stage',STEPS,key='tx_step')
  entry=next(x for x in steps if x['step']==step)
  st.subheader(f'{STEPS.index(step)+1:02} · {step}')
  st.caption('Requirements to review with your team')
  for task in entry['requirements']:st.checkbox(task,key=f'tx_{industry}_{framework}_{step}_{task}',disabled=True)
  st.caption('Link authoritative evidence and approval records through the existing Decision OS workspaces. Checkboxes remain read-only until an authenticated integration exists.')
 with right:
  st.subheader('Screen Guide')
  st.write('**What is required?**')
  st.write('Document the requirements and responsible owner before moving forward.')
  st.write('**Who approves?**')
  st.write('An independent authorized human is required.' if entry['human_gate'] else 'A reviewer validates the recorded assessment.')
  st.write('**What does AI do?**')
  st.write('Explain evidence, identify gaps and draft recommendations; never approve or execute.')
  q=st.text_input('Ask about this stage',key='tx_question')
  if q:st.info(f'For {step}, start with the listed evidence and responsible reviewer. I cannot assess the truth of an unconnected record. Your question: {q[:160]}')
 st.divider()
 st.caption('Decision OS graph and certification engines remain backend-owned; this view does not create verified facts.')
