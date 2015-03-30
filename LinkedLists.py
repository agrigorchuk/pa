# Some linked lists tasks
class Node:
    def __init__(self, val, pNext = None):
        self.m_value = val
        self.p_next = pNext

def printListLinear(pRoot):
    ''' Prints list '''
    tmp = pRoot
    while tmp is not None:
        print(tmp.m_value)
        tmp = tmp.p_next

def printImmutableListInReverseOrder(pRoot):
    ''' Prints list in reverse order w/o changing it '''
    if pRoot is None:
        return
    printImmutableListInReverseOrder(pRoot.p_next)
    print(pRoot.m_value)

def reverseListRecursive(node):
    ''' Reverses linked list and returns it '''
    temp = None
    if not node.p_next: return node
    else:
        temp = reverseListRecursive(node.p_next)
        node.p_next.p_next = node
        node.p_next = None
    return temp

def mergeSortedLinkedLists(list1, list2):
    ''' Merges two sorted linked lists'''
    if list1 is None: return list2
    if list2 is None: return list1
    if list1.m_value < list2.m_value:
        list1.m_next = mergeSortedLinkedLists(list1.m_next, list2)
        return list1
    else:
        list2.m_next = mergeSortedLinkedLists(list2.m_next, list1)
        return list2

lst1 = Node(1, Node(2, Node(3, Node(4, Node(5)))))
lst2 = Node(3, Node(5, Node(8, Node(11, Node(19)))))
lstMerged = mergeSortedLinkedLists(lst1, lst2)

root = Node(1, Node(2, Node(3, Node(4, Node(5, Node(6))))))

printListLinear(root)
printImmutableListInReverseOrder(root)
