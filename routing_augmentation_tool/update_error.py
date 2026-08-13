import re
with open("app_valhalla.py", "r") as f:
    content = f.read()

replacement = """
            else:
                error_msg = f"Valhalla API Error {resp.status_code}: {resp.text}"
                print(error_msg)
                st.error(error_msg)
                st.stop() # Stop execution if routing API fails so they see the error clearly
        except Exception as e:
            error_msg = f"Valhalla Request Failed: {e}"
            print(error_msg)
            st.error(error_msg)
            st.stop()
"""

content = re.sub(
    r"""            else:
                print\(f"Valhalla API Error: \{resp\.status_code\}"\)
        except Exception as e:
            print\(f"Valhalla Request Failed: \{e\}"\)""",
    replacement, content
)

with open("app_valhalla.py", "w") as f:
    f.write(content)
