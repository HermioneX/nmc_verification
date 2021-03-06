import nmc_verification
import numpy as np
from nmc_verification.nmc_vf_base import IV

def tc(ob, fo, grade_list=None):
    '''
    accuracy 求多分类预报准确率
    :param ob: 实况数据 不确定维numpy
    :param fo:  预测数据 不确定维numpy
    :param grade_list:等级，如果grade_list= None则ob和fo里的值代表类别，否则，根据grade_list来进行分类
    :return: 返回一维数组，包括（总样本数，正确数）
    '''
    # 多分类预报准确率
    if grade_list is None:
        # ob 和fo是不确定维的numpy数组，其中每个值是代表分类的类别
        ob1 = ob.reshape((-1))
        fo1 = fo.reshape((-1))
    else:
        ob1 = np.zeros_like(ob)
        fo1 = np.zeros_like(fo)
        # ob 和fo 是连续的变量，通过 threshold_list 将ob 和fo划分成连续的等级之后再计算等级准确性
        for index in range(len(grade_list) - 1):
            ob_index_list = np.where((grade_list[index] <= ob) & (ob < grade_list[index + 1]))
            ob1[ob_index_list] = index+1
            fo_index_list = np.where((grade_list[index] <= fo) & (fo < grade_list[index + 1]))
            fo1[fo_index_list] = index+1
        ob_index_list = np.where(grade_list[-1] <= ob)
        ob1[ob_index_list] = len(grade_list)
        fo_index_list = np.where(grade_list[-1] <= fo)
        fo1[fo_index_list] = len(grade_list)
    correct_num = np.sum(fo1 == ob1)
    return np.array([ob.size, correct_num])

def tcof(ob,fo,grade_list):

    '''
    多分类评分中间统计量
    :param ob: 实况数据 任意维numpy数组
    :param fo: 预测数据 任意维numpy数组,Fo.shape 和Ob.shape一致
    :param grade_list: 一个从小到大排列的实数列表，以其中列出的数值划分出的多个区间作为分类标签。
    :return: 一维数组，包括（总样本数，正确样本数，观测的
    '''
    tc1 = tc(ob, fo, grade_list)
    ft = nmc_verification.nmc_vf_method.multi_category.table.frequency_table(ob, fo, grade_list)
    tcof1 = np.zeros((len(grade_list)+2,2))
    tcof1[0,:] = tc1
    tcof1[1:,:] = ft.T
    return tcof1

def accuracy(ob, fo, grade_list=None):
    '''
    accuracy 求多分类预报准确率
    :param ob: 实况数据 任意维numpy数组
    :param fo: 预测数据 任意维numpy数组,Fo.shape 和Ob.shape一致
    :param grade_list: 如果该参数为None，观测或预报值出现过的值都作为分类标记.
    如果该参数不为None，它必须是一个从小到大排列的实数，以其中列出的数值划分出的多个区间作为分类标签。
    对于预报和观测值不为整数的情况，grade_list 不能设置为None。
    :return: 0-1的实数，0代表无技巧，最优预报为1
    '''
    tc1 = tc(ob,fo,grade_list)
    total_count = tc1[0]
    correct_count = tc1[1]
    accuracy_score = correct_count / total_count
    return accuracy_score

def accuracy_tc(tc_array):
    '''
    :param tc_array:
    :return:
    '''
    total_count = tc_array[...,0]
    correct_count = tc_array[...,1]
    accuracy_score = correct_count / total_count
    return accuracy_score

def accuracy_tcof(tcof_array):
    '''

    :param tcof_array:
    :return:
    '''
    total_count = tcof_array[...,0,0]
    correct_count = tcof_array[...,0,1]
    accuracy_score = correct_count / total_count
    return accuracy_score

def hss(ob,fo,grade_list = None):
    '''
    hss heidke技能得分,它表现实际的预报的分类准确性相对于随机分类达到的准确性的技巧
    :param ob: 实况数据 任意维numpy数组
    :param fo: 预测数据 任意维numpy数组,Fo.shape 和Ob.shape一致
    :param grade_list: 如果该参数为None，观测或预报值出现过的值都作为分类标记.
    如果该参数不为None，它必须是一个从小到大排列的实数，以其中列出的数值划分出的多个区间作为分类标签。
    对于预报和观测值不为整数的情况，grade_list 不能设置为None。
    :return:
    '''
    conf_mx = nmc_verification.nmc_vf_method.multi_category.table.contingency_table_multicategory(ob,fo,grade_list)
    accuracy_score = accuracy(ob, fo, grade_list)
    total_num = ob.size
    NF_array = conf_mx[0:-1,-1]
    NO_array = conf_mx[-1,0:-1]
    random_score = np.dot(NF_array,NO_array) /(total_num * total_num)
    if (random_score == 1):
        HSS = IV
    else:
        HSS = (accuracy_score - random_score)/(1 - random_score)
    return HSS


def hk(ob, fo, grade_list=None):
    '''
    hk Hanssen和Kuipers判别
    :param ob: 实况数据 任意维numpy数组
    :param fo: 预测数据 任意维numpy数组,Fo.shape 和Ob.shape一致
    :param grade_list: 如果该参数为None，观测或预报值出现过的值都作为分类标记.
    如果该参数不为None，它必须是一个从小到大排列的实数，以其中列出的数值划分出的多个区间作为分类标签。
    对于预报和观测值不为整数的情况，grade_list 不能设置为None。
    :return:
    '''
    # 多分类预报hk技巧评分
    conf_mx = nmc_verification.nmc_vf_method.multi_category.table.contingency_table_multicategory(ob,fo,grade_list)
    accuracy_score = accuracy(ob, fo, grade_list)
    total_num = ob.size
    NF_array = conf_mx[0:-1,-1]
    NO_array = conf_mx[-1,0:-1]
    random_score = np.dot(NF_array,NO_array) /(total_num * total_num)
    ob_rate = np.dot(NO_array,NO_array)/(total_num * total_num)
    HK = (accuracy_score - random_score)/(1 - ob_rate)

    return HK

def hk_tcof(tcof_array):
    '''
    :param tcof_array:
    :return:
    '''

    tc_sum = tcof_array[...,0,0]
    cc_sum = tcof_array[...,0,1]
    accuracy_score = cc_sum / tc_sum
    obn_sum = tcof_array[...,1:,0]
    fon_sum = tcof_array[...,1:,1]
    dotobfo = np.zeros_like(tc_sum)
    dotobob = np.zeros_like(tc_sum)
    for g in range(obn_sum.shape[-1]):
        dotobfo += obn_sum[...,g] * fon_sum[...,g]
        dotobob += obn_sum[...,g] * obn_sum[...,g]
    random_score = dotobfo /(tc_sum * tc_sum)
    ob_rate = dotobob/(tc_sum * tc_sum)
    if ob_rate.size == 1:
        if ob_rate == 1:
            HK = IV
        else:
            HK = (accuracy_score - random_score) / (1 - ob_rate)
    else:
        ob_rate[ob_rate == 1] = -1
        HK = (accuracy_score - random_score)/(1 - ob_rate)
        HK[ob_rate == -1] = IV
    return HK

def hss_tcof(tcof_array):
    '''

    :param tcof_list:
    :return:
    '''
    tc_sum = tcof_array[...,0,0]
    cc_sum = tcof_array[...,0,1]
    accuracy_score = cc_sum / tc_sum
    obn_sum = tcof_array[...,1:,0]
    fon_sum = tcof_array[...,1:,1]
    dotobfo = np.zeros_like(tc_sum)
    dotobob = np.zeros_like(tc_sum)
    for g in range(obn_sum.shape[-1]):
        dotobfo += obn_sum[...,g] * fon_sum[...,g]
        dotobob += obn_sum[...,g] * obn_sum[...,g]
    random_score = dotobfo /(tc_sum * tc_sum)

    if random_score.size == 1:
        if random_score == 1:
            HSS= IV
        else:
            HSS = (accuracy_score - random_score) / (1 - random_score)
    else:
        random_score[random_score == 1] = -1
        HSS = (accuracy_score - random_score)/(1 - random_score)
        HSS[random_score == -1] = IV

    return HSS


