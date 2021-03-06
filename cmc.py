#!/usr/bin/python2
# -*- coding: utf-8 -*-

import numpy as np
import random
from scipy.spatial.distance import cdist
import numpy.matlib as matlib
import cPickle as pickle
from xml.dom.minidom import Document
import os
import matplotlib.pyplot as plt
import csv
import sys
from sklearn.metrics import average_precision_score, precision_recall_curve, auc


def _cmc_core(D, G, P):
    m, n = D.shape
    order = np.argsort(D, axis=0)
    match = (G[order] == P)  # G[order],按距离排序的矩阵，第一行为top1,从左到右为各plabel对应的glabel
    return (match.sum(axis=1) * 1.0 / n).cumsum()  # 从上至下累积求和


def count(distmat, glabels=None, plabels=None, n_selected_labels=None, n_repeat=100):
    """Compute the Cumulative Match Characteristic(CMC)
    Args:
        distmat: A ``m×n`` distance matrix. ``m`` and ``n`` are the number of
            gallery and probe samples, respectively. In the case of ``glabels``
            and ``plabels`` both are ``None``, we assume both gallery and probe
            samples to be unique, i.e., the i-th gallery samples matches only to
            the i-th probe sample.
        glabels: Vector of length ``m`` that represents the labels of gallery
            samples
        plabels: Vector of length ``n`` that represents the labels of probe
            samples
        n_selected_labels: If specified, we will select only part of all the
            labels to compute the CMC.
        n_repeat: The number of random sampling times
    Returns:
        A vector represents the average CMC
    """

    m, n = distmat.shape

    if glabels is None and plabels is None:
        glabels = np.arange(0, m)
        plabels = np.arange(0, n)

    if type(glabels) is list:
        glabels = np.asarray(glabels)
    if type(plabels) is list:
        plabels = np.asarray(plabels)

    unique_glabels = np.unique(glabels)

    if n_selected_labels is None:
        n_selected_labels = unique_glabels.size

    ret = 0
    for r in range(n_repeat):
        # Randomly select gallery labels
        ind = np.random.choice(unique_glabels.size,
                               n_selected_labels,
                               replace=False)
        ind.sort()
        g = unique_glabels[ind]

        # Select corresponding probe samples
        ind = []
        for i, label in enumerate(plabels):
            if label in g: ind.append(i)
        ind = np.asarray(ind)

        p = plabels[ind]

        # Randomly select one sample per selected label
        subdist = np.zeros((n_selected_labels, p.size))
        for i, glabel in enumerate(g):
            samples = np.where(glabels == glabel)[0]
            j = np.random.choice(samples)
            subdist[i, :] = distmat[j, ind]

        # Compute CMC
        ret += _cmc_core(subdist, g, p)

    return ret / n_repeat


def count_lazy(distfunc, glabels=None, plabels=None, n_selected_labels=None, n_repeat=100):
    """Compute the Cumulative Match Characteristic(CMC) in a lazy manner
    This function will only compute the distance when needed.
    Args:
        distfunc: A distance computing function. Denote the number of gallery
            and probe samples by ``m`` and ``n``, respectively.
            ``distfunc(i, j)`` should output distance between gallery sample
            ``i`` and probe sample ``j``. In the case of ``glabels``
            and ``plabels`` both are integers, ``m`` should be equal to ``n``
            and we assume both gallery and probe samples to be unique,
            i.e., the i-th gallery samples matches only to the i-th probe
            sample.
        glabels: Vector of length ``m`` that represents the labels of gallery
            samples. Or an integer ``m``.
        plabels: Vector of length ``n`` that represents the labels of probe
            samples. Or an integer ``n``.
        n_selected_labels: If specified, we will select only part of all the
            labels to compute the CMC.
        n_repeat: The number of random sampling times
    Returns:
        A vector represents the average CMC
    """

    if type(glabels) is int:
        m = glabels
        glabels = np.arange(0, m)
    elif type(glabels) is list:
        glabels = np.asarray(glabels)
        m = glabels.size
    else:
        m = glabels.size

    if type(plabels) is int:
        n = plabels
        plabels = np.arange(0, n)
    elif type(plabels) is list:
        plabels = np.asarray(plabels)
        n = plabels.size
    else:
        n = plabels.size

    unique_glabels = np.unique(glabels)

    if n_selected_labels is None:
        n_selected_labels = unique_glabels.size

    ret = 0
    for r in range(n_repeat):
        # Randomly select gallery labels
        ind = np.random.choice(unique_glabels.size,
                               n_selected_labels,
                               replace=False)
        ind.sort()
        g = unique_glabels[ind]

        # Select corresponding probe samples
        ind = []
        for i, label in enumerate(plabels):
            if label in g: ind.append(i)
        ind = np.asarray(ind)

        p = plabels[ind]

        # Randomly select one sample per selected label
        subdist = np.zeros((n_selected_labels, p.size))
        for i, glabel in enumerate(g):
            samples = np.where(glabels == glabel)[0]
            j = np.random.choice(samples)
            for k in range(p.size):
                subdist[i, k] = distfunc(j, ind[k])

        # Compute CMC
        ret += _cmc_core(subdist, g, p)

    return ret / n_repeat


def compute_distmat(gallery, probe):
    """
    compute distance of each image feature pairs in gallery and probe, L2 norm
    :param gallery:     gallery image features, 2D ndarray(number of gallery x feature dim)
    :param probe:       probe image features, 2D ndarray(number of probe x feature dim)
    :return:            distance mat, 2D ndarray (number of gallery x number of probe)
    """
    return cdist(gallery, probe)


def sorted_image_names(distmat, g_name_array, top_n):
    """
    Based on distance mat, return sorted gallery image names.
    Input distmat is an ndarray(n_gallery x n_probe), result is (n_probe x top_n),
    each row represents a quary result of that probe.
    :param distmat:         distance mat, 2D ndarray (n_gallery x n_probe)
    :param g_name_array:    name of gallery images, must be a 1D ndarray (1 x n_gallery)
    :param top_n:           number of images that matches each probe image
    :return:                the top n images matches each probe image, 2D ndarray (n_probe x top_n)
    """
    distmat = np.transpose(distmat)
    m, n = distmat.shape
    if n > top_n:
        order = np.argsort(distmat, axis=1)[:, :top_n]
    else:
        order = np.argsort(distmat, axis=1)
    return g_name_array[order]


def _map_core(D, G, P, top_n):
    m, n = D.shape
    order = np.argsort(D, axis=0)
    match = (G[order] == P)  # G[order],按距离排序的矩阵，第一行为top1,从左到右为各plabel对应的glabel
    cump = match.cumsum(0) * 1.0 / matlib.repmat(np.arange(1, m + 1, 1).reshape([m, 1]), 1, n)  # 从上至下累积求和
    p = (match * cump)[:top_n]
    ap = p.sum(axis=0) / match[:top_n].sum(0)
    ap[np.isnan(ap)] = 0
    return ap.mean()


def mAP(distmat, glabels=None, plabels=None, top_n=None, n_repeat=10):
    """Compute the Mean Average Precision(MAP)
    Args:
        distmat: A ``m×n`` distance matrix. ``m`` and ``n`` are the number of
            gallery and probe samples, respectively. In the case of ``glabels``
            and ``plabels`` both are ``None``, we assume both gallery and probe
            samples to be unique, i.e., the i-th gallery samples matches only to
            the i-th probe sample.
        glabels: Vector of length ``m`` that represents the labels of gallery
            samples
        plabels: Vector of length ``n`` that represents the labels of probe
            samples
        top_n: Select only part of all the labels to compute.
        n_repeat: The number of random sampling times
    Returns:
        A float number represents the MAP
    """
    m, n = distmat.shape
    if glabels is None and plabels is None:
        glabels = np.arange(0, m)
        plabels = np.arange(0, n)
    if type(glabels) is list:
        glabels = np.asarray(glabels)
    if type(plabels) is list:
        plabels = np.asarray(plabels)

    unique_glabels = np.unique(glabels)
    if top_n is None:
        top_n = unique_glabels.size
    ret1 = 0
    # for r in range(n_repeat):
    #     # Randomly select gallery labels
    #     ind = np.random.choice(unique_glabels.size,
    #                            top_n,
    #                            replace=False)
    #     ind.sort()
    #     g = unique_glabels[ind]
    #
    #     # Select corresponding probe samples
    #     ind = []
    #     for i, label in enumerate(plabels):
    #         if label in g: ind.append(i)
    #     ind = np.asarray(ind)
    #
    #     p = plabels[ind]
    #
    #     # Randomly select one sample per selected label
    #     subdist = np.zeros((top_n, p.size))
    #     for i, glabel in enumerate(g):
    #         samples = np.where(glabels == glabel)[0]
    #         j = np.random.choice(samples)
    #         subdist[i, :] = distmat[j, ind]
    #
    #     # Compute MAP
    #     ret1 += _map_core(subdist, g, p, top_n)
    # ret1 = ret1 / n_repeat

    ret2 = _map_core(distmat, glabels, plabels, top_n)

    distmat = distmat.transpose()
    ret1 = mean_ap(distmat, plabels, glabels)

    return ret1, ret2


def mean_ap(distmat, query_ids=None, gallery_ids=None, query_cams=None, gallery_cams=None):
    m, n = distmat.shape
    # Fill up default values
    if query_ids is None:
        query_ids = np.arange(m)
    if gallery_ids is None:
        gallery_ids = np.arange(n)
    if query_cams is None:
        query_cams = np.zeros(m).astype(np.int32)
    if gallery_cams is None:
        gallery_cams = np.ones(n).astype(np.int32)
    # Ensure numpy array
    query_ids = np.asarray(query_ids)
    gallery_ids = np.asarray(gallery_ids)
    query_cams = np.asarray(query_cams)
    gallery_cams = np.asarray(gallery_cams)
    # Sort and find correct matches 按行获得从小到大排序的索引值
    indices = np.argsort(distmat, axis=1)
    matches = (gallery_ids[indices] == query_ids[:, np.newaxis])
    print matches
    # Compute AP for each query
    aps = []
    for i in range(m):
        # Filter out the same id and same camera
        valid = ((gallery_ids[indices[i]] != query_ids[i]) |
                 (gallery_cams[indices[i]] != query_cams[i]))
        y_true = matches[i][valid]
        y_score = -distmat[i][indices[i]][valid]
        if not np.any(y_true): continue
        aps.append(average_precision_score(y_true, y_score))
    if len(aps) == 0:
        raise RuntimeError("No valid query")
    return np.mean(aps)


def normalize(nparray):
    # nparray: number * dim
    nparrayt = np.transpose(nparray)
    npsum = np.sum(nparrayt * nparrayt, axis=0)
    npsum[np.isnan(npsum)] = 0.0001
    nparrayt = nparrayt / np.sqrt(npsum)
    nparraytt = np.transpose(nparrayt)
    return nparraytt


def pick_top(distmat, contain_top_n):
    print('contain_top: %s' % contain_top_n)
    order = np.argsort(distmat, axis=0)
    dis_max = distmat.max()
    for row in range(contain_top_n):
        for col in range(distmat.shape[1]):
            distmat[order[row][col]][col] -= dis_max
    for row in range(contain_top_n, distmat.shape[0]):
        for col in range(distmat.shape[1]):
            distmat[order[row][col]][col] = dis_max - distmat[order[row][col]][col]
    return distmat


def train_1000_mAP(normalize_flag=False, contain_top_n=None):
    print('train_1000_mAP(normalize_flag=%s, contain_top_n=%s)' % (normalize_flag, contain_top_n))
    # valid mAP
    g = np.load('VGG_model/result/test_features/train_1000_gallery_features.npy')
    g_labels = np.load('VGG_model/result/test_features/train_1000_gallery_labels.npy')
    p = np.load('VGG_model/result/test_features/train_1000_probe_features.npy')
    p_labels = np.load('VGG_model/result/test_features/train_1000_probe_labels.npy')
    if normalize_flag:
        g = normalize(g)
        p = normalize(p)
    distmat = compute_distmat(g, p)
    if contain_top_n is not None:
        distmat = pick_top(distmat, contain_top_n=contain_top_n)
    map1, map2 = mAP(distmat, glabels=g_labels, plabels=p_labels, top_n=200)
    print('train_1000 map: %f, %f ' % (map1, map2))


def valid_mAP(normalize_flag=False, contain_top_n=None):
    print('valid_mAP(normalize_flag=%s, contain_top_n=%s)' % (normalize_flag, contain_top_n))
    min_step = 100000000
    max_step = 0
    for root, dirs, files in os.walk(os.path.abspath('./VGG_model/result/test_features')):
        for name in files:
            if 'valid_probe_features_step-' in name:
                step = int(name.split('.')[0].split('-')[-1])
                if step > max_step:
                    max_step = step
                if step < min_step:
                    min_step = step
    map2_all = []
    # valid mAP
    for step in range(min_step, max_step + 1, 5000):
        g = np.load('VGG_model/result/test_features/valid_gallery_features_step-%d.npy' % step)
        print('step: %s, g_feature abs mean : %s' % (step, np.mean(np.abs(g))))
        g_labels = np.load('VGG_model/result/test_features/valid_gallery_labels_step-%d.npy' % step)
        p = np.load('VGG_model/result/test_features/valid_probe_features_step-%d.npy' % step)
        p_labels = np.load('VGG_model/result/test_features/valid_probe_labels_step-%d.npy' % step)
        if normalize_flag:
            g = normalize(g)
            p = normalize(p)
        distmat = compute_distmat(g, p)
        if contain_top_n is not None:
            distmat = pick_top(distmat, contain_top_n=contain_top_n)
        map1, map2 = mAP(distmat, glabels=g_labels, plabels=p_labels, top_n=200)
        map2_all.append(map2)
        print('step: %d, map: %f, %f ' % (step, map1, map2))
    plt.plot(range(min_step, max_step + 1, 5000), map2_all)
    plt.show()


def create_xml(pname, gnames, xml_path):
    doc = Document()
    message = doc.createElement('Message')
    message.setAttribute('Version', '1.0')
    doc.appendChild(message)

    info = doc.createElement('Info')
    info.setAttribute('evaluateType', '11')
    info.setAttribute('mediaFile', 'PedestrianRetrieval')
    message.appendChild(info)

    items = doc.createElement('Items')
    message.appendChild(items)

    for i, item_name in enumerate(pname):
        item = doc.createElement('Item')
        item.setAttribute('imageName', str(item_name).zfill(6))
        gname_str = ''
        for gname in gnames[i]:
            gname_str += (str(gname).zfill(6) + ' ')
        gname_str = gname_str[:-1]
        item.appendChild(doc.createTextNode(gname_str))
        items.appendChild(item)

    fp = open(xml_path, 'w')
    doc.writexml(fp, addindent='  ', newl='\n')


def generate_first_predict_xml(normalize_flag=False, contain_top_n=None):
    print('generate_predict_xml(normalize_flag=%s, contain_top_n=%s)' % (normalize_flag, contain_top_n))
    g = np.load('VGG_model/result/test_features/predict_gallery_features.npy')
    p = np.load('VGG_model/result/test_features/predict_probe_features.npy')
    g_order = np.load('VGG_model/result/test_features/predict_gallery_orders.npy')
    p_order = np.load('VGG_model/result/test_features/predict_probe_orders.npy')
    if normalize_flag:
        g = normalize(g)
        p = normalize(p)
    if False in (g_order == np.array(range(58061))):
        print('g_order error')
        return
    if False in (p_order == np.array(range(4480))):
        print('p_order error')
        return
    g_names_list = []
    g_names_order_list = []
    with open('data/predict_gallery_name.csv', "r") as f:
        for name_order in f.readlines():
            name_order = name_order.strip('\n')
            g_names_list.append(int(name_order.split(',')[0]))
            g_names_order_list.append(float(name_order.split(',')[1]))
    g_names = np.array(g_names_list)
    g_names_order = np.array(g_names_order_list)
    p_names_list = []
    p_names_order_list = []
    with open('data/predict_probe_name.csv', "r") as f:
        for name_order in f.readlines():
            name_order = name_order.strip('\n')
            p_names_list.append(int(name_order.split(',')[0]))
            p_names_order_list.append(float(name_order.split(',')[1]))
    p_names = np.array(p_names_list)
    p_names_order = np.array(p_names_order_list)
    if False in (g_names_order == np.array(range(58061))):
        print('g_names_order error')
        return
    if False in (p_names_order == np.array(range(4480))):
        print('p_names_order error')
        return
    print('start compute distance')
    distmat = compute_distmat(g, p)
    if contain_top_n is not None:
        distmat = pick_top(distmat, contain_top_n=contain_top_n)
    print('start sort')
    sort_g_names_top_n = sorted_image_names(distmat, g_names, top_n=300)
    np.save('data/sort_g_names_top_n.npy', sort_g_names_top_n)
    print('start create xml')
    create_xml(p_names, sort_g_names_top_n[:, :200], 'data/predict_result.xml')
    generate_top_predict_csv()


def generate_top_predict_csv():
    print('generate_top_predict_csv()')
    sort_g_names_top_n = np.load('data/sort_g_names_top_n.npy')
    probe_num = sort_g_names_top_n.shape[0]
    gallery_num = sort_g_names_top_n[1]

    # generate predict_repeat
    with open('data/predict_repeat_probe.csv', 'w') as output:
        with open('data/predict_probe.csv', 'rb') as f:
            label = 0
            for row in csv.reader(f):
                for j in range(len(gallery_num)):
                    output.write("%s,%s,%s" % (row[0], label, row[2]))
                    output.write("\n")
                    label += 1
    gallery_folder_path = os.path.join(sys.path[0], 'data/new_online_vali_set_UPLOAD_VERSION/vr_path')
    with open('data/predict_repeat_gallery.csv', 'w') as output:
        label = 0
        for row in sort_g_names_top_n:
            for i, element in enumerate(row):
                path = os.path.join(gallery_folder_path, str(element).zfill(6)) + '.jpg'
                output.write("%s,%s,%s" % (path, label, i))
                output.write("\n")
                label += 1


if __name__ == '__main__':
    # train_1000_mAP(normalize_flag=True)
    # valid_mAP(normalize_flag=True)
    generate_first_predict_xml(normalize_flag=True)
    # have to
    # 1. delete xml's first line(<?xml version="1.0"?>)
    # 2. delete last line(nothing in last line)
    # 3. add a space in the second line, after "PedestrianRetrieval"
    #    so the second line will be:<Info evaluateType="11" mediaFile="PedestrianRetrieval" />
    # 4. the xml's size is 6.4 MB (6,433,396 bytes)
