import xlsxwriter
import csv

def create_xlsx(listToConvert, name):
    if (name[-5:]!=".xlsx"):
        name = name+".xlsx"        
    wb = xlsxwriter.Workbook(name,  {'constant_memory': True})
    sh = wb.add_worksheet()
    for i in range(len(listToConvert)):
        for j in range(len(listToConvert[i])):
            row = i
            col = j
            cnt = listToConvert[i][j]
            sh.write(row,col,cnt)
    wb.close()
    return name

def create_csv(listToConvert, name):
        if (name[-4:]!=".csv"):
                name = name+".csv"
        isManyDimensionsTable = False
        for i in range(len(listToConvert)):
                if (type(listToConvert[i])==list):
                        isManyDimensionsTable = True
                        break
        if (isManyDimensionsTable==False):
                listToConvertV2 = []
                for elmt in listToConvert:
                        listToConvertV2.append([elmt])
                return createCSV(listToConvertV2, name)
        with open(name, 'a') as optTable:
                writercsv=csv.writer(optTable, delimiter='\t', lineterminator = '\n')
                writercsv.writerows(listToConvert)      
        return name

def csv_to_table(csv_file, remove_header=True):
    with open(csv_file, 'r') as file:
        reader = csv.reader(file, delimiter='\t')
        table = []
        for i, row in enumerate(reader):
            if remove_header and i == 0:
                continue  # skip header row
            table.append(row)
    return table
