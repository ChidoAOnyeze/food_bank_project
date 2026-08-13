Anonymize Routed Orders CSV
================================

Usage
-----

Run the anonymizer from the `routing_augmentation_tool` folder:

```bash
python anonymize_orders.py input.csv [output.csv]
```

If `output.csv` is omitted the script writes `input_anonymized.csv` alongside
the input. `Name` replacements are deterministic (hashed) so no external mapping
file is created or required.

What it does
-----------
- Removes personal/address columns (Work Order Number, Customer Number, Memo,
  Address, City, State, Zip, FixedTime, OrderDate, Total Quantity, EqCode,
  Open1, Close1, Pattern1, Filler, Shipment Date, Standing Appointment,
  County, Delivery Instructions, Static Appointment).
- Replaces `Name` with deterministic labels like `Site_00001`.
- Converts `OrderType`: `Cold` -> `A`, `Dry` -> `B`.

Notes
-----
- The script uses the CSV header names present in the provided file. If your
  CSV has slightly different header names (for example `Pattern` instead of
  `Pattern1`), edit `anonymize_orders.py` `DROP_COLUMNS` list accordingly.
