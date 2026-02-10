# Squash
Squash is the process of identifying equivalent rows in a csv file and merging them together. This should be built so that if a csv has multiple rows with the same values in certain columns, but different values in the other columns, it will squash those rows into a single row (or potentially more) with the user guiding the application on what values to put in the squashed row.

## Workflow
- User navigates to the Squash feature in the Wrangle sub menu.
- User will be asked if squashed rows should be output to a separate file for review. If yes, the user will be prompted to provide a name for the output file. If no, then squashed rows will be lost upon completion of the squash process.
- User will then be asked to select the columns that should be used to uniquely identify rows. 
- Application will then begin the process of squashing rows with the users help. The application should iterate over each row of the csv file and check if there are any other rows with the same values in the selected columns (all must be equivalent).
- Application will display the rows that are being squashed together and ask the user to fill out the values for the squashed row.
- The application should attempt a best effort squash by filling out the values for the squashed row with the most common value in each column. The user can then edit these values as they see fit.
- Once the user has filled out the values for the squashed row, the application will save the squashed row and move on to the next set of rows that need to be squashed together.
- Everytime a row is squashed, the application should output the squashed rows to the separate file if the user chose to output squashed rows to a separate file. This should be done as the process is happening, not at the end of the process, so that if the user needs to stop the process for any reason, they will still have a record of the squashed rows up to that point.

