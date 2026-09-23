Option Explicit

'Returns CacheDir whether defined name is a constant (=""C:\KPCache"") or a cell reference.
Private Function GetCacheDir() As String
    On Error GoTo Fallback
    Dim nm As Name
    Set nm = ThisWorkbook.Names("CacheDir")
    Dim refers As String
    refers = nm.RefersTo

    'If it refers to a range, read the value
    If InStr(1, refers, "!", vbTextCompare) > 0 Then
        GetCacheDir = CStr(nm.RefersToRange.Value)
        If Len(GetCacheDir) > 0 Then Exit Function
    End If

    'Constant like =""C:\KPCache""
    refers = Replace(refers, "=", "")
    refers = Replace(refers, Chr$(34), "")
    refers = Trim$(refers)
    If Len(refers) > 0 Then
        GetCacheDir = refers
        Exit Function
    End If

Fallback:
    GetCacheDir = "C:\KPCache"
End Function



Public Sub RunDetailedAnalysis_5000()
    Call RunDetailedAnalysisWithLimit(5000)
End Sub

Public Sub RunDetailedAnalysis_ALL()
    Call RunDetailedAnalysisWithLimit(0)
End Sub

Private Sub RunDetailedAnalysisWithLimit(maxRows As Long)
    Debug.Print "========================================"
    If maxRows > 0 Then
        Debug.Print "DETAILED CONNECTIVITY (" & maxRows & " sequences)"
    Else
        Debug.Print "DETAILED CONNECTIVITY (ALL sequences)"
    End If
    Debug.Print "========================================"
    Debug.Print ""
    
    On Error GoTo ErrorHandler
    
    Dim t As Double
    t = Timer
    
    Dim cacheDir As String
    cacheDir = GetCacheDir()
    On Error Resume Next
    Environ$("KPCACHEDIR") = cacheDir
    On Error GoTo ErrorHandler

    
    Application.StatusBar = "Creating optimized script..."
    
    Dim scriptPath As String
    scriptPath = cacheDir & "\detailed_analysis.py"
    
    Dim fso As Object
    Set fso = CreateObject("Scripting.FileSystemObject")
    
    Dim file As Object
    Set file = fso.CreateTextFile(scriptPath, True)
    
    file.WriteLine "import pandas as pd"
    file.WriteLine "import numpy as np"
    file.WriteLine "import xlwings as xw"
    file.WriteLine "import os"
    file.WriteLine ""
    file.WriteLine "CACHE_DIR = os.environ.get('KPCACHEDIR', r'C:\\KPCache')"
    file.WriteLine ""
    file.WriteLine "print('Reading cache files...')"
    file.WriteLine "dates = pd.read_parquet(os.path.join(CACHE_DIR, 'vim_dates.parquet'))"
    file.WriteLine "base = pd.read_parquet(os.path.join(CACHE_DIR, 'dbaspd_base.parquet'))"
    file.WriteLine "merged = dates.merge(base, on='VimRow')"
    file.WriteLine ""
    file.WriteLine "print('Reading PlTbl and building lookups...')"
    file.WriteLine "wb = xw.Book.caller()"
    file.WriteLine "cil = wb.sheets['CIL']"
    file.WriteLine "pltbl = cil.tables['PlTbl'].range.options(pd.DataFrame, header=1, index=False).value"
    file.WriteLine ""
    file.WriteLine "# Normalize PlTbl"
    file.WriteLine "pltbl.columns = [c.strip().upper() for c in pltbl.columns]"
    file.WriteLine "pltbl['PLANET'] = pltbl['PLANET'].str.strip().str.title()"
    file.WriteLine ""
    file.WriteLine "# Pre-build lookup dictionaries (MUCH faster than repeated queries)"
    file.WriteLine "wtdscore_dict = {}"
    file.WriteLine "wtdscore_nossl_dict = {}"
    file.WriteLine "nl_dict = {}"
    file.WriteLine ""
    file.WriteLine "for _, row in pltbl.iterrows():"
    file.WriteLine "    planet = row['PLANET']"
    file.WriteLine "    wtdscore_dict[planet] = float(row.get('WTDSCORE', 0)) if pd.notna(row.get('WTDSCORE')) else 0.0"
    file.WriteLine "    wtdscore_nossl_dict[planet] = float(row.get('WTDSCORE_NOSSL', 0)) if pd.notna(row.get('WTDSCORE_NOSSL')) else 0.0"
    file.WriteLine "    "
    file.WriteLine "    # Build set of all NL-type planets for this planet"
    file.WriteLine "    nl_set = set()"
    file.WriteLine "    for col in ['NL', 'NLOFNL', 'NLOFSL', 'NLOFSSL']:"
    file.WriteLine "        if col in pltbl.columns:"
    file.WriteLine "            val = row.get(col)"
    file.WriteLine "            if pd.notna(val):"
    file.WriteLine "                nl_set.add(str(val).strip().title())"
    file.WriteLine "    nl_dict[planet] = nl_set"
    file.WriteLine ""
    file.WriteLine "print('Lookups built for', len(wtdscore_dict), 'planets')"
    file.WriteLine ""
    file.WriteLine "transit = pd.to_datetime(wb.names['TransitDate'].refers_to_range.value)"
    file.WriteLine "merged['DasaDate'] = pd.to_datetime(merged['DasaDate'])"
    file.WriteLine "future = merged[merged['DasaDate'] >= transit].sort_values('VimRow')"
    
    If maxRows > 0 Then
        file.WriteLine "future = future.head(" & maxRows & ")"
    End If
    
    file.WriteLine "print('Processing', len(future), 'sequences')"
    file.WriteLine ""
    file.WriteLine "# Add end date and end row"
    file.WriteLine "future['EndRow'] = future['VimRow'].shift(-1)"
    file.WriteLine "future['EndDate'] = future['DasaDate'].shift(-1)"
    file.WriteLine "future = future[future['EndDate'].notna()].copy()"
    file.WriteLine "future['EndRow'] = future['EndRow'].astype(int)"
    file.WriteLine ""
    file.WriteLine "# Calculate duration"
    file.WriteLine "future['DurDays'] = (future['EndDate'] - future['DasaDate']).dt.total_seconds() / 86400"
    file.WriteLine "future['DurYears'] = future['DurDays'] / 365.25"
    file.WriteLine "future['DurMonths'] = future['DurYears'] * 12"
    file.WriteLine ""
    file.WriteLine "print('Computing connectivity (optimized)...')"
    file.WriteLine ""
    file.WriteLine "def analyze_fast(dbaspd):"
    file.WriteLine "    s = str(dbaspd).strip().ljust(12)"
    file.WriteLine "    levels = [s[i:i+2].strip().title() for i in range(0, 12, 2)]"
    file.WriteLine "    md = levels[0]"
    file.WriteLine "    if not md: return None"
    file.WriteLine "    "
    file.WriteLine "    # Consecutive connectivity"
    file.WriteLine "    conn = [1 if levels[i] == md else 0 for i in range(6)]"
    file.WriteLine "    "
    file.WriteLine "    # Stop at first 0"
    file.WriteLine "    for i in range(1, 6):"
    file.WriteLine "        if conn[i] == 0:"
    file.WriteLine "            for j in range(i+1, 6):"
    file.WriteLine "                conn[j] = 0"
    file.WriteLine "            break"
    file.WriteLine "    "
    file.WriteLine "    levels_connected = sum(conn)"
    file.WriteLine "    "
    file.WriteLine "    # Count NL-type connections"
    file.WriteLine "    nl_set = nl_dict.get(md, set())"
    file.WriteLine "    freq_nltype = sum(1 for tok in levels if tok in nl_set)"
    file.WriteLine "    "
    file.WriteLine "    return {"
    file.WriteLine "        'Planet': md,"
    file.WriteLine "        'IMD': conn[0],"
    file.WriteLine "        'AD': conn[1],"
    file.WriteLine "        'PD': conn[2],"
    file.WriteLine "        'SU': conn[3],"
    file.WriteLine "        'PRANA': conn[4],"
    file.WriteLine "        'DEH': conn[5],"
    file.WriteLine "        'LevelsConnected': levels_connected,"
    file.WriteLine "        'Freq_Total': levels_connected,"
    file.WriteLine "        'Freq_NLType': freq_nltype,"
    file.WriteLine "        'Score': levels_connected * 10,"
    file.WriteLine "        'WTDSCORE': wtdscore_dict.get(md, 0.0),"
    file.WriteLine "        'WTDSCORE_NOSSL': wtdscore_nossl_dict.get(md, 0.0)"
    file.WriteLine "    }"
    file.WriteLine ""
    file.WriteLine "# Process all (vectorized where possible)"
    file.WriteLine "results = []"
    file.WriteLine "for idx, row in future.iterrows():"
    file.WriteLine "    conn = analyze_fast(row['DBASPD'])"
    file.WriteLine "    if conn:"
    file.WriteLine "        results.append({"
    file.WriteLine "            'StartRow': row['VimRow'],"
    file.WriteLine "            'EndRow': row['EndRow'],"
    file.WriteLine "            'DBASPD': row['DBASPD'],"
    file.WriteLine "            'StartDate': row['DasaDate'],"
    file.WriteLine "            'EndDate': row['EndDate'],"
    file.WriteLine "            'DurDays': round(row['DurDays'], 2),"
    file.WriteLine "            'DurYears': round(row['DurYears'], 2),"
    file.WriteLine "            'DurMonths': round(row['DurMonths'], 2),"
    file.WriteLine "            **conn"
    file.WriteLine "        })"
    file.WriteLine ""
    file.WriteLine "output = pd.DataFrame(results)"
    file.WriteLine ""
    file.WriteLine "cols = ['Planet', 'IMD', 'AD', 'PD', 'SU', 'PRANA', 'DEH', "
    file.WriteLine "        'LevelsConnected', 'Freq_Total', 'Freq_NLType', 'Score', "
    file.WriteLine "        'WTDSCORE', 'WTDSCORE_NOSSL', "
    file.WriteLine "        'StartRow', 'EndRow', 'StartDate', 'EndDate', "
    file.WriteLine "        'DurDays', 'DurYears', 'DurMonths']"
    file.WriteLine "output = output[cols]"
    file.WriteLine "output = output.sort_values(['StartDate', 'LevelsConnected'], ascending=[True, False])"
    file.WriteLine ""
    file.WriteLine "print('Writing output...')"
    
    Dim outputFile As String
    If maxRows > 0 Then
        outputFile = cacheDir & "\\DetailedConnectivity.csv"
    Else
        outputFile = cacheDir & "\\DetailedConnectivity_ALL.csv"
    End If
    
    file.WriteLine "OUTPUT_CSV = r\"" & outputFile & "\""
    file.WriteLine "output.to_csv(OUTPUT_CSV, index=False)"
    file.WriteLine "print('Done! Wrote', len(output), 'rows')"
    
    file.Close
    
    Debug.Print "Running optimized analysis..."
    Application.StatusBar = "Running (should be ~10 seconds)..."
    
    RunPython "exec(open(r'C:\KPCache\detailed_analysis.py').read())"
    
    Application.StatusBar = False
    
    Debug.Print ""
    Debug.Print "? Complete in: " & Format(Timer - t, "0.0") & " seconds"
    Debug.Print "  Output: " & outputFile
    Debug.Print "========================================"
    
    MsgBox "Complete!" & vbCrLf & outputFile & vbCrLf & _
           "Time: " & Format(Timer - t, "0.0") & " sec", vbInformation
    
    Exit Sub
    
ErrorHandler:
    Application.StatusBar = False
    Debug.Print "? ERROR: " & Err.Description
    MsgBox "Error: " & Err.Description, vbCritical
End Sub

