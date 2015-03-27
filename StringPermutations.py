def printPermutations(inputStr, partStr='', resultList = []):
    '''Print all permutations of the word with * -> ahmed, ahme*, ahm*d, ahm**, ah*ed, ah*e*, ah**d, ah***, a*med, a*me*, a*m*d, a*m**, a**ed'''
    if len(inputStr) == 0:
        resultList.append(partStr)
        return
    else:
        printPermutations(inputStr[1:], partStr+inputStr[0], resultList)
        printPermutations(inputStr[1:], partStr+'*', resultList)

def printPemutationsAccToDictionary(inputStr, partStr='', resultList = []):
    '''Print all permutations of string representation 123 -> abc, aw, lc'''
    if len(inputStr) == 0:
        resultList.append(partStr)
        return
    else:
        # Grab one or two symbols and proceed further
        # Grab one symbol
        ch = chr(int(inputStr[0])+96)
        printPemutationsAccToDictionary(inputStr[1:], partStr+ch, resultList) 
        if len(inputStr) >=2:
            val = int(inputStr[0:2])
            if val <= 26:
                ch2 = chr(val+96)
                # Grab two symbols
                printPemutationsAccToDictionary(inputStr[2:], partStr+ch2, resultList) 

resultList1 = []
printPemutationsAccToDictionary('123', '', resultList1)
resultList2 = []
printPermutations('ahmed', '', resultList2)
