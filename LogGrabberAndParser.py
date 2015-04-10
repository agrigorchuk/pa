import sys
import os
import re
import argparse
import string
import fnmatch
import pymssql
import collections
import datetime
from sets import Set
from subprocess import call
import pickle

# DB Constants (used only if copyFiles variable set to True)
sqlStatement = "SELECT Host + substring(LogFile, 8, 1000), 'MCEngineLogs\' + substring(LogFile, 25, patindex('%%log\Eagle\%%', LogFile) - 25) FROM dbo.ProcessInstance WHERE ProcessNumber IN (SELECT DISTINCT ProcessNumber 	FROM dbo.TradeState WHERE ContextId IN (%s) )"

copyFiles = False
# Regular expression predefinitions to get match when StaticContext cache was loaded or not
reStaticContextMiss   = re.compile(r'(.{17}).*WRN:\s+\d+\s+\d+ StaticContext cache file missing') 
reStaticContextLoaded = re.compile(r'(.{17}).*ContextFactory') 
reSPCall                = re.compile(r'(.{21}).*sp(\w+\.\w+).*([0-9\.]+)')
successDictDumpFileName = 'success-dict.dmp'
failedDictDumpFileName  = 'failed-dict.dmp'
spCallsDictDumpFileName = 'spcalls-dict.dmp'
############################
# Main routine             #
############################
def main():
    args = parse_argv()

    filesForProcessing = []
    successLoadsDict = {}
    failedLoadsDict = {}
    spCallsDict = {}
    if copyFiles is True:
        print('Starting LOG files copying...')
        requestAndCopyFiles(args.working_dir, args.sql_instance, args.database, sqlStatement % args.contexts)
        print('LOG files copying is DONE')

    if args.restore is True:
        print('Restoring earlier parsed data...')
        #import pdb;pdb.set_trace()
        successLoadsDict = pickle.load(open(args.working_dir+successDictDumpFileName, 'rb'))
        failedLoadsDict = pickle.load(open(args.working_dir+failedDictDumpFileName,'rb'))
        spCallsDict = pickle.load(open(args.working_dir+spCallsDictDumpFileName, 'rb'))
        print('Done')
    else:
        print('Loking for LOG files in '+args.working_dir+' ...')
        filesForProcessing = getFilesForProcessing(args.working_dir)
        for currentFile in filesForProcessing:
            print('Processing file '+currentFile)
            findStaticContextAndSPLoads(currentFile,successLoadsDict, failedLoadsDict, spCallsDict)
        pickle.dump(successLoadsDict, open(args.working_dir+successDictDumpFileName, 'wb'))
        pickle.dump(failedLoadsDict, open(args.working_dir+failedDictDumpFileName, 'wb'))
        pickle.dump(spCallsDict, open(args.working_dir+spCallsDictDumpFileName, 'wb'))
        print('LOG parsing is done')

    print('Aggregating results...')
    # Aggregation using internal algorithm
    aggregatedSuccess={}
    aggregatedFailed={}
    aggregatedSPCalls = {}
    for kSuccess in successLoadsDict:
        newSuccessArr = [parse_date(currElm) for currElm in successLoadsDict[kSuccess]]
        aggregatedSuccess[kSuccess] = aggregate_withDelta(newSuccessArr, args.aggr_delta)

    for kFailed in failedLoadsDict:
        newFailedArr = [parse_date(currElm) for currElm in failedLoadsDict[kFailed]]
        aggregatedFailed[kFailed] = aggregate_withDelta(newFailedArr, args.aggr_delta)

    aggregatedSPCalls = aggregateSPCalls(spCallsDict, args.aggr_delta)

    print('Merging results...')
    mergedAggr = merge_(aggregatedSuccess, aggregatedFailed)

    print('Dumping results...')
    dumpData(args.aggregated_dump, mergedAggr, aggregatedSPCalls)

    print('All job is done, exit')

############################
# Helper functions section #
############################

def dumpData(fileName, mergedDictionary, spCallsDictionary):
    "Dumps result dictionary (mergedDictionary) to CSV file (fileName)"

    with open(fileName, 'w') as f:
        f.writelines('when;success;failed\n')
        for currDay in sorted(mergedDictionary):
            for currElm in sorted(mergedDictionary[currDay]):
                tpl = mergedDictionary[currDay][currElm]
                currString = str(currElm)+str(';')+str(tpl[0])+str(';')+str(tpl[1])
                f.write(currString+'\n')
    with open('spcalls-'+fileName, 'w') as f:
        f.writelines('when;number_of_sp_calls;total_exec_time\n')
        for currDay in spCallsDictionary.keys():
            currTpl = spCallsDictionary[currDay];
            currString = currDay.strftime('%d/%m/%y %H:%M:%S')+str(';')+str(currTpl[0])+str(';')+str(currTpl[1])
            f.write(currString+'\n')

def merge_(successDict, failedDict):
    "Merges 2 dictionaries"
    days = set(successDict.keys())
    days.update(failedDict.keys())
    mergedDict = {}

    for day in days:
        mergedDict[day] = {}
        successLoads = successDict.get(day, {})
        failedLoads = failedDict.get(day, {})
        times = set(successLoads.keys())
        times.update(failedLoads.keys())
        for time in times:
            mergedDict[day][time] = (successLoads.get(time, 0), failedLoads.get(time, 0))

    return mergedDict

def aggregate_withDelta(arr, deltaInSeconds):
    "Aggregates to dictionary with deltaInSeconds"
    if not arr:
        return None
    else:
        currDT = arr[0]
    resultDict = {}
    seconds = [t.hour*3600+t.minute*60+t.second for t in arr]
    for currSecont in seconds:
        startDate = currDT
        bin = currSecont/deltaInSeconds*deltaInSeconds
        hour = (bin)/3600
        minute = (bin-hour*3600)/60
        second = bin-hour*3600-minute*60
        startDate = startDate.replace(hour=hour, minute=minute, second=second)
        resultDict[startDate] = resultDict.setdefault(startDate,0)+1
    return resultDict

def parse_date(str_date):
    return datetime.datetime.strptime(str_date, '%d/%m/%y %H:%M:%S')

def parse_date_time_ms(str_date):
    return datetime.datetime.strptime(str_date, '%d/%m/%y %H:%M:%S.%f')

def requestAndCopyFiles(workDir, sqlInstance, database, sqlStatement):
    "Get From SQL Server and call xcopy"
    sqlConnection = pymssql.connect(host=sqlInstance, database=database)
    sqlCursor = sqlConnection.cursor()
    sqlCursor.execute(sqlStatement)
    for currRow in sqlCursor:
        currDestDir = workDir+currRow[1]
        call(['xcopy', '\\\\'+currRow[0], currDestDir])

def getFilesForProcessing(workDir):
    "Fill array of files to be processed, not filling it during xcopy for cases when xcopy execution finished with error"            
    localFilesForProcessing = []
    for root, dirnames, filenames in os.walk(workDir):
        for filename in fnmatch.filter(filenames, '*.log'):
            localFilesForProcessing.append(os.path.join(root, filename))
    return localFilesForProcessing

def findStaticContextAndSPLoads(fileName, successLoads, failedLoads, spLoads):
    "Opens, reads line-by-line log and fills successLoads, failedLoads arrays"
    with open(fileName, "r") as currFileHandle:
        for currLine in currFileHandle:
            # StaticContext Load match/not match
            successMatch = reStaticContextLoaded.match(currLine)
            if successMatch is not None:
                result = successMatch.group(1)
                currDtKey = parse_date(result).replace(hour=0, minute=0, second=0)
                successLoads.setdefault(currDtKey, []).append(result)
            else:
                failMatch = reStaticContextMiss.match(currLine)
                if failMatch is not None:
                    result = failMatch.group(1)
                    currDtKey = parse_date(result).replace(hour=0, minute=0, second=0)
                    failedLoads.setdefault(currDtKey, []).append(result)
                else:
                    # Same routine for SP call
                    spCallSuccessMatch = reSPCall.match(currLine)
                    if spCallSuccessMatch is not None:
                        wholeString = spCallSuccessMatch.group(0)
                        resultSplit = wholeString.split(' ')
                        occurenceDT = parse_date_time_ms(spCallSuccessMatch.group(1))
                        spName      = spCallSuccessMatch.group(2)
                        numeric = float(resultSplit[-1])
                        tpl = (occurenceDT, numeric)
                        spLoads.setdefault(spName, []).append(tpl)


def aggregateSPCalls(spCallsDict, aggrDelta):
    "Aggregate SP calls"
    occurencies = []
    resultDict = {}
    processed = False
    for currSP in spCallsDict.keys():
        for currOccurency in spCallsDict[currSP]:
            occurencies.append((currOccurency[0].hour*3600+currOccurency[0].minute*60+currOccurency[0].second,currOccurency[1]))
            if not processed:
                currDT = currOccurency[0]
                processed = True
    resultDict = {}
    for currSecond in occurencies:
        startDate = currDT
        bin = currSecond[0]/aggrDelta*aggrDelta
        hour = (bin)/3600
        minute = (bin-hour*3600)/60
        second = bin-hour*3600-minute*60
        startDate = startDate.replace(hour=hour, minute=minute, second=second)
        if startDate in resultDict.keys():
            resultDict[startDate] = (resultDict[startDate][0]+1,resultDict[startDate][1]+currSecond[1])
        else:
            resultDict[startDate] = (1,currSecond[1])
        #resultDict[startDate] = resultDict.setdefault(startDate,(0,0))+(1,currSecond[1])

    return collections.OrderedDict(sorted(resultDict.items()))


def parse_argv():
    global copyFiles
    #global workDir, copyFiles, agrregateDeltaSeconds, detailedDumpFileName, aggregatedDumpFileName, sqlInstance, database
    parser = argparse.ArgumentParser(description='Analyses MCEngine logs for StaticContext loads/misses',formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--working-dir', '-w', required=True, help='Path to MCEngine logs dir')
    parser.add_argument('--restore', '-r', type=bool, required=False, default='', help='Says to script restore from serialised objects and just regenerate aggregation')
    parser.add_argument('--copy-files', '-c', type=bool, required=False, default=False, help='Raise SQL Request, gather MCEngine logs from SCRIPT (SSO used for SQL server auth)')
    parser.add_argument('--contexts', '-ctx', required=False, default='', help='Comma sepparated list of Contexts for SQL Query (example "19356,19323,19523", PLEASE NOTE THAT NO SPACES AFTER COMA)')
    parser.add_argument('--aggr-delta', '-d', type=int, required=False, default=60, help='Aggregation delta in seconds')
    parser.add_argument('--aggregated-dump', '-ad',  required=False, default='statistics-aggr.csv', help='Aggregated CSV file name')
    parser.add_argument('--sql-instance', '-i',  required=False, default='LDNPSM050000089\\CREDS_MAIN1_LIVE', help='SQL Server instance name')
    parser.add_argument('--database', '-db',  required=False, default='CREDS', help='SQL Server DB Name')

    args = parser.parse_args()
    if args.contexts is not '':
        copyFiles = True

    return args

if __name__ == '__main__':
    print('Created by Oleksandr Hryhorchuk 26/01/2015')
    print('oleksandr.hryhorchuk@barclays.com - For questions')
    main()
