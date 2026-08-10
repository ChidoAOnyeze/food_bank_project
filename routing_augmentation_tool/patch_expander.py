import re

with open('app.py', 'r') as f:
    content = f.read()

old_code = """    st.subheader("Input Data")
    st.dataframe(df)"""

new_code = """    with st.expander("View Raw Input Data", expanded=False):
        st.dataframe(df)"""

content = content.replace(old_code, new_code)

with open('app.py', 'w') as f:
    f.write(content)

