# Split Join Plan
## Overview
Split-Join is a new feature to add to the CSV-ME. It allows users to split a row into into multiple rows based on user specified criteria. The user will be able to define an output record (the new rows to be created in the output csv) and how to map each row into the new rows. The nuance is that they can actually create multiple output rows from a single row in the input csv. They will also be able to specify which column values are common and should be copied into the new row for all the new split rows from a single input row.

## Workflow
1. The user will select the "Split-Join" option from the list of available transformations
2. The user will be prompted to define the new row headers (the columns for the new rows to be created) for the output csv.
3. The user will then be prompted on how to define the mapping from the input row to the new output rows.
- First, the user will be asked if they want to specify which columns are common and should be copied into the new rows for all the new split rows from a single input row. One column at a time, they will map to the new column in the output csv.
- Then, the user will be asked to define how to split the row into multiple new rows. The prompt should say something along the lines of "Output Row 1 <column name>: <input column name>". The when all the output columns have been mapped, they will then be asked to map more output rows from the same input row; "Output Row 2 <column name>: <input column name>". This will continue until the user is done mapping output rows from the same input row. 
- For all mapping, if the user does not want to map a column, they can just leave the input column name blank and it will be left empty in the output csv.



