for filename in ["app_valhalla_road_path.py", "app_valhalla.py", "app.py"]:
    with open(filename, "r") as f:
        content = f.read()

    # 1. Main stops CSV
    target_stops = "df = pd.read_csv(io.BytesIO(file_bytes))"
    replacement_stops = "df = pd.read_csv(io.BytesIO(file_bytes))\n    df.columns = df.columns.astype(str).str.strip()"
    if target_stops in content and "df.columns = df.columns.astype(str).str.strip()" not in content:
        content = content.replace(target_stops, replacement_stops)
        print(f"Added header stripping for stops df in {filename}")

    # 2. Trucks CSV (if present)
    target_trucks = "tdf = pd.read_csv(uploaded_trucks)"
    replacement_trucks = "tdf = pd.read_csv(uploaded_trucks)\n                    tdf.columns = tdf.columns.astype(str).str.strip()"
    if target_trucks in content and "tdf.columns = tdf.columns.astype(str).str.strip()" not in content:
        content = content.replace(target_trucks, replacement_trucks)
        print(f"Added header stripping for trucks tdf in {filename}")

    with open(filename, "w") as f:
        f.write(content)

