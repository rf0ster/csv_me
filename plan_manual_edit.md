# Manual Edit
CSV-ME should implement the following feature.

## Overview
The manual edit feature allows users jump through csvs lightning fast based on search criteria across coloumns. If the search criteria is met, the user should be presented with all the keypair of column and values for the row that matches the criteria. The user can then naviage through the the different column values for that row and edit them as they see fit. Once the user is done, a new csv file should be generated with their changes.

## Workflow
- User is given the option Manual Edit on the main menu.
- User is prompted to enter search criteria for any number of columns. Look at how the split-join feature is implemented for extracting search criteria.  
- Once the user has entered their search criteria, the program should iterate one row at a time through the csv file and check if the search criteria is met. If it is, the user should be presented with all the keypair of column and values for that row that matches the criteria.
- The user can then navigate through the different column values for that row and edit them as they see fit.
- The user should also have the option to add a new row once they are done editing the current row.
- If they select yes, a new row should appear with the original values (pre-edit) for the new row. The user can then edit the values for the new row as they see fit.
