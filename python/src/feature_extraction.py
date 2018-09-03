"""This code simulates the feature extraction part of the connectivity model.
"""
import nibabel as nib
import numpy as np
import scipy
import scipy.signal
import sklearn

import iterative_pca
import utils.utils as util
import constants

# TODO(loya) make sure and remove these two
import numpy.matlib as matlib
import sklearn.decomposition


def run_group_ica_separately(cifti_image, BM, threshold=2, num_ic=40, N=91282):
    # TODO num_ic, N, consts: figure out and rename.
    """Runs a group ICA for each hemisphere separately
    :param left_hemisphere_data:
    :param right_hemisphere_data:
    :param BM:
    :param num_ic: number of independent components
    :param threshold:
    :return:
    """
    # TODO (Itay) cifti_image to left_hemisphere_data and right_hemisphere_data
    left_hemisphere_data = cifti_extract_data(cifti_image, BM, 'L')
    right_hemisphere_data = cifti_extract_data(cifti_image, BM, 'R')
    # np.transpose(left_hemisphere_data)
    # np.transpose(right_hemisphere_data)
    # Compute ICA , check threshold CONST

    # left_ica,_,_ = sklearn.decomposition.fastica(left_hemisphere_data,num_ic)
    # right_ica,_,_ = sklearn.decomposition.fastica(right_hemisphere_data,num_ic)
    # load ICA from MATLAB check threshold = 2
    ica_LH_dict = scipy.io.loadmat('ica_LH_test.mat')
    left_ica = ica_LH_dict['ica_LH']
    ica_RH_dict = scipy.io.loadmat('ica_RH_test.mat')
    right_ica = ica_RH_dict['ica_RH']

    # flip signs (large tail on the right)
    # left_ica = np.multiply(left_ica,
    #                    np.tile(np.sign(np.sum(np.sign(np.multiply(left_ica, (np.abs(left_ica) > ICA_FUCKING_CONST).astype(float))), 1))
    #                        ,(1, left_ica.shape[1])))
    # right_ica = np.multiply(right_ica,
    #                    np.tile(np.sign(np.sum(np.sign(np.multiply(right_ica, (np.abs(right_ica) > ICA_FUCKING_CONST).astype(float))), 1))
    #                        ,(1, right_ica.shape[1]))
    thresh = (np.abs(left_ica) > threshold).astype(np.float64)
    ica_time_thresh = np.multiply(left_ica, thresh)
    end_res = np.sign(np.sum(np.sign(ica_time_thresh), 1))
    end_res_t = np.reshape(end_res, (num_ic, 1))
    tile_res = np.tile(end_res_t, (1, left_ica.shape[1]))
    left_ica = np.multiply(left_ica, tile_res)

    thresh = (np.abs(right_ica) > threshold).astype(float)
    ica_time_thresh = np.multiply(right_ica, thresh)
    end_res = np.sign(np.sum(np.sign(ica_time_thresh), 1))
    end_res_t = np.reshape(end_res, (num_ic, 1))
    tile_res = np.tile(end_res_t, (1, right_ica.shape[1]))
    right_ica = np.multiply(right_ica, tile_res)

    # keep ICA components that have L/R symmetry
    # left-right DICE of cortical ICs to
    # 1) re-order the ICs
    # 2) select the ICs that are found in both hemispheres
    x = np.zeros([32492, left_ica.shape[0]])
    y = np.zeros([32492, right_ica.shape[0]])
    x[np.ix_(list(BM[0].surface_indices), list(range(x.shape[1])))] = np.transpose(left_ica)
    y[np.ix_(list(BM[1].surface_indices), list(range(y.shape[1])))] = np.transpose(right_ica)

    D = dice(x > threshold, y > threshold)
    D_threshold = (D == np.transpose(np.matlib.repmat(np.amax(D, 1), D.shape[1], 1))).astype(np.float64)
    D_tmp = ((D * D_threshold) == np.matlib.repmat(np.amax(D * D_threshold, axis=0), D.shape[1], 1))
    D_threshold = D_tmp * D_threshold

    # TODO(Itay) just for tests, delete the next line:
    # D_threshold[np.ix_(list(range(0,36)),[0])] = np.ones((36,1))
    # just for test, delete the prev line

    r = np.nonzero(np.sum(D_threshold, 1))[0]
    c = D_threshold.argmax(1)
    c = c[r]
    # save
    x = np.zeros((N, len(r)))
    x[np.ix_(list(BM[0].data_indices), list(range(x.shape[1])))] = np.transpose(left_ica[r, :])
    x[np.ix_(list(BM[1].data_indices), list(range(len(c))))] = np.transpose(right_ica[c, :])

    # scipy.io.savemat('ica_LR_MATCHED_test.mat', {'ica_LR_MATCHED_test': np.transpose(x)})

    return np.transpose(x)


def cifti_extract_data(cifti_image, BM, side):
    '''extracts data from cifti images'''
    if (side == 'L'):
        indices = BM[0].data_indices
        data = cifti_image[:, indices.start:indices.stop]
    else:
        if (side == 'R'):
            indices = BM[1].data_indices
            data = cifti_image[:, indices.start:indices.stop]
        else:
            if (side == 'both'):
                data = cifti_image
            else:
                print('error: bad cifti_extract_data command, side is not L, R or both')
    return data


def dice(x, y):
    """gets x = N*nx and y = N*ny and return nx*ny
    :param x should be N*nx:
    :param y should be N*ny:
    :return: nx*ny
    """
    if (x.shape[0] != y.shape[0]):
        print('x and y incompatible (dice)')
    nx = x.shape[1]
    ny = y.shape[1]
    # xx = np.tile(np.sum(x,0),(ny,1))
    # yy = np.tile(np.sum(y,0), (nx,1))
    xx = np.matlib.repmat(np.sum(x, 0), ny, 1)
    yy = np.matlib.repmat(np.sum(y, 0), nx, 1)

    temp = np.dot(np.transpose(x.astype(np.float64)), y.astype(np.float64))
    res = 2 * np.divide(temp, xx + yy)
    return res


def run_group_ica_together(cifti_image, BM, threshold=2, num_ic=50):
    # TODO num_ic, N, consts: figure out and rename.
    """Runs a group ICA for both hemispheres, to use as spatial filters.
    :param both_hemisphere_data:
    :param num_ic:
    :return:
    """
    both_hemisphere_data = cifti_extract_data(cifti_image, BM, 'both')
    # np.transpose(both_hemisphere_data)
    both_ica, _, _ = sklearn.decomposition.fastica(both_hemisphere_data, num_ic)
    thresh = (np.abs(both_ica) > threshold).astype(float)
    ica_time_thresh = np.multiply(both_ica, thresh)
    end_res = np.sign(np.sum(np.sign(ica_time_thresh), 1))
    end_res_t = np.reshape(end_res, (num_ic, 1))
    tile_res = np.tile(end_res_t, (1, both_ica.shape[1]))
    both_ica = np.multiply(both_ica, tile_res)

    return np.transpose(both_ica)


def run_dual_regression(left_right_hemisphere_data, BM, subjects, size_of_g=91282):
    """Runs dual regression TODO(whoever) expand and elaborate.

    Updates the cifti image in every subject.
    :param left_right_hemisphere_data:
    :param subjects:
    :param size_of_g:
    """

    single_hemisphere_shape = left_right_hemisphere_data.shape[1]
    print(single_hemisphere_shape)
    G = np.zeros([size_of_g, single_hemisphere_shape * 2])
    hemis = np.zeros([size_of_g, single_hemisphere_shape * 2])

    G[BM[0].data_indices, :single_hemisphere_shape] = left_right_hemisphere_data[BM[0].data_indices, :]
    G[BM[1].data_indices, single_hemisphere_shape: 2 * single_hemisphere_shape] = left_right_hemisphere_data[
                                                                                  BM[1].data_indices, :]

    hemis[BM[0].data_indices, :single_hemisphere_shape] = 1
    hemis[BM[1].data_indices, single_hemisphere_shape: 2 * single_hemisphere_shape] = 1

    g_pseudo_inverse = np.linalg.pinv(G)
    for subject in subjects:
        subject_data = []
        print("NUM OF SESSIONS:", len(subject.sessions))
        for session in subject.sessions:
            normalized_cifti = sklearn.preprocessing.scale(session.cifti.transpose(), with_mean=False)
            deterended_data = np.transpose(scipy.signal.detrend(np.transpose(normalized_cifti)))
            subject_data.append(deterended_data)
        subject_data = np.concatenate(subject_data, axis=1)
        T = g_pseudo_inverse @ subject_data

        t = util.fsl_glm(np.transpose(T), np.transpose(subject_data))
        subject.left_right_hemisphere_data = np.transpose(t) * hemis



def get_subcortical_parcellation(cifti_image, brain_maps):
    """Get sub-cortical parcellation using atlas definitions and current data.
    :return: (no. voxel, cortical parcellation parts)
    """

    def do_nothing_brain_map_handler(*args):
        pass

    def use_as_is_brain_map_handler(cifti_image, current_map):
        """Uses the brain map with no prepossessing
        :param cifti_image:
        :param current_map:
        :return: numpy array (no. voxels, 1), 1 if index is in part of the current part, 0 otherwise
        """
        ret = np.zeros([cifti_image.shape[1], 1])
        ret[current_map.data_indices] = 1
        return ret

    def corrcoef_and_spectral_ordering(mat):
        """Implementation of reord2 + corrcoef function that was used in the matlab version
        :param mat: The data matrix
        :return: spectral ordering of the corrcoef matrix of A
        """
        mat = np.corrcoef(mat.transpose()) + 1
        ti = np.diag(np.sqrt(1. / np.sum(mat, 0)))
        W = np.matmul(np.matmul(ti, mat), ti)
        U, S, V = np.linalg.svd(W)
        S = np.diag(S)
        P = np.multiply(np.matmul(ti, np.reshape(U[:, 1], [U.shape[0], 1])), np.tile(S[1, 1], (U.shape[0], 1)))
        return P

    def half_split_using_corrcoef_and_spectral_ordering_brain_map_handler(cifti_image, current_map):
        """This split the data into 2 different clusters using corrcoef,
        spatial ordering, and positive\negative split
        :param cifti_image:
        :param current_map:
        :return: numpy array (no. voxels , 2), each vector is a 0\1 vector representing the 2 clusters
        """
        res = np.zeros([cifti_image.shape[1], 2])
        cifti_current_map_data = cifti_image[:, current_map.data_indices]
        spatial_ordering = corrcoef_and_spectral_ordering(cifti_current_map_data)
        res[current_map.data_indices, :] = np.hstack((spatial_ordering > 0, spatial_ordering < 0)).astype(float)
        return res

    def label_to_function(label):
        label = label.rsplit('_', 1)[0]
        labels_to_function = {
            'CIFTI_STRUCTURE_CORTEX': do_nothing_brain_map_handler,
            'CIFTI_STRUCTURE_ACCUMBENS': use_as_is_brain_map_handler,
            'CIFTI_STRUCTURE_AMYGDALA': half_split_using_corrcoef_and_spectral_ordering_brain_map_handler,
            'CIFTI_STRUCTURE_BRAIN': do_nothing_brain_map_handler,
            'CIFTI_STRUCTURE_CAUDATE': half_split_using_corrcoef_and_spectral_ordering_brain_map_handler,
            'CIFTI_STRUCTURE_CEREBELLUM': ica_clustering_brain_map_handler,
            'CIFTI_STRUCTURE_DIENCEPHALON_VENTRAL': do_nothing_brain_map_handler,
            'CIFTI_STRUCTURE_HIPPOCAMPUS': half_split_using_corrcoef_and_spectral_ordering_brain_map_handler,
            'CIFTI_STRUCTURE_PALLIDUM': use_as_is_brain_map_handler,
            'CIFTI_STRUCTURE_PUTAMEN': half_split_using_corrcoef_and_spectral_ordering_brain_map_handler,
            'CIFTI_STRUCTURE_THALAMUS': ica_clustering_brain_map_handler,
        }
        return labels_to_function[label]

    def ica_clustering_brain_map_handler(cifti_image, current_map):
        """This split the data into 3 parts by counting the eddect of each of the 3 first components
        in the ICA analysis on all the voxels, and determines the cluster by the one with the maximum
        connection to the voxel.
        :param cifti_image:
        :param current_map:
        :return: numpy array (no. voxels , 3), each vector is a 0\1 vector representing the 3 clusters
        """
        cifti_current_map_data = cifti_image[:, current_map.data_indices]
        # todo(kess) this FastICA does not yield the same result as
        ica_y, _, _ = sklearn.decomposition.fastica(cifti_current_map_data, 3, )

        thresh = np.asarray(np.abs(ica_y) > constants.ICA_FUCKING_CONST, dtype=np.float32)
        ica_time_thresh = ica_y * thresh
        end_res = np.sign(np.sum(np.sign(ica_time_thresh), axis=1))
        end_res_reshaped = np.reshape(end_res, (3, 1))
        end_res_t = np.matlib.repmat(end_res_reshaped, 1, ica_y.shape[1])
        ica_y = ica_y * end_res_t

        res = np.zeros([cifti_image.shape[1], ica_y.shape[0]])
        res[current_map.data_indices, :] = ica_y.transpose()
        return res

    sub_cortex_clusters = []
    for current_map in brain_maps:
        x = label_to_function(current_map.brain_structure_name)(cifti_image, current_map)
        if x is not None:
            sub_cortex_clusters.append(x)
    return np.hstack(sub_cortex_clusters).transpose()


def get_semi_dense_connectome(semi_dense_connectome_data, subjects):
    """Final feature extraction (forming semi-dense connectome)
    For each subject, load RFMRI data, then load ROIs from above to calculate semi-dense connectome.

    # ASSUMES:
    # getting a subject list holding session array sessions, each holding left h. data, right h. data, ROIs, BM and CIFTI.
    # In MATLAB they're all being loaded. All these members are assumed to be numpy arrays.
    # (This is handled as an object but can be changed to a list of tuples or dictionary, whatever)

    :return: A dictionary from a subject to its correlation coeff.
    """
    subject_to_correlation_coefficient = {}
    # TODO(loya) shapes must be validated.
    for subject in subjects:
        W = []
        print("SHAPES:",
              "left_right_hemisphere_data:", subject.left_right_hemisphere_data.shape,
              "semi_dense_connectome_data:", semi_dense_connectome_data.shape)
        ROIS = np.concatenate([subject.left_right_hemisphere_data, semi_dense_connectome_data], axis=1)
        print("ROIS.shape:", ROIS.shape)
        for session in subject.sessions:
            # TODO(loya) this transpose was added as a patch, when fixed completely change back.
            W.append(sklearn.preprocessing.scale(session.cifti).transpose())
        # TODO(loya) this might cause a bug.
        print("W[0].shape before concat:", W[0].shape)
        W = np.concatenate(W, axis=1)
        print("W SHAPE AFTER CONCAT:", W.shape)
        # MULTIPLE REGRESSION
        # TODO(loya) there was a transpose here that caused a bug. removed because for now, might be a problem.
        print("ROIS pinv shape:", np.linalg.pinv(ROIS).shape)
        T = np.linalg.pinv(ROIS) @ W
        print("T shape:", T.shape)
        # CORRELATION COEFFICIENT
        F = sklearn.preprocessing.normalize(T, axis=1) @ np.transpose(sklearn.preprocessing.normalize(W, axis=0))
        print("F.shape:", F.shape)
        subject_to_correlation_coefficient[subject] = F
    return subject_to_correlation_coefficient


def extract_features(subjects, pca):
    # TODO need to extract features from multiple subjects here.

    # TODO some things might be repeatedly ask to calculate, like ica_LR_MATCHED ie. we might want provide it instead,
    # TODO so that the featureExtroctor class in the prediction job is to calculate it before hand and save it.
    pass


def get_spatial_filters(filters):
    """Gets the filters (a result of the ica on the pca result), uses threshold and do winner-take-all
    The returned matrix is an index matrix which is MATLAB compatible.
    """
    m = np.amax(filters, axis=1)  # TODO(loya) validate cdata is the same.

    # +1 for MATLAB compatibility
    wta = np.argmax(filters, axis=1) + 1
    wta = wta * (m > constants.SPATIAL_FILTERS_CONST)

    S = np.zeros_like(filters)
    for i in range(filters.shape[1]):
        # +1 for MATLAB compatibility
        S[:, i] = (wta == i+1).astype(float)
    return S