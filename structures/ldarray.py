import numpy as np
import datetime as dt
from collections import OrderedDict
import time
from copy import deepcopy as dcopy

def round_to_multiple(value, multiple=1):
    """ Rounds value to nearest multiple. Multiple can be greater or less than 1.

        Example:
            round_to_float(7.77777, 1e-3) --> 7.778

            round_to_float(7.77777, 3)    --> 9.0    
    """

    invmul = 1/multiple

    r1 = value/multiple
    w = r1//1
    w = np.where((r1%1) >= 0.5, w+1, w)
    
    mlog10 = np.log10(multiple)
    
    if mlog10 > 0:
        return w/invmul
    else:
        return np.around(w/invmul, int(np.abs(mlog10)))

def check_shapes(a, b):
    ## check that the shape length of a and b match
    if len(a) != len(b):
        return False
    
    ## check that the length of each dimension matches
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    
    return True


class lddim(OrderedDict):
    """ Labeled dimension indices for ldarray. Conditions values to work as indices, but otherwise, same as 
        an Ordered Dictionary. 

        Accepts a key-value pair 'idx_precision' that will not be included in dictionary, 
        but can be optionally used to specify index precision for each dimension. Value of idx_precision is
        a dictionary with keys matching the lddim keys and values that will override the default precision
        for that dimension.
        
        Example:
            dim = lddim(a=[1.2, 2.4, 3.1], b=[4,5,6], idx_precision={'a':1e-6})

            dim = lddim(a=[1.2, 2.4, 3.1], b=[4,5,6], idx_precision={'a':2})

        Index precision can also be modified after the constructor is called:

            dim.set_precision(b=2, a=1e-3)
    """
    DEFAULT_PRECISION = 1e-6

    def __init__(self, **kwargs):
        ## Pop idx_precison from kwargs. Floating point indices default to 6 decimal precision.
        self.idx_precision = kwargs.pop('idx_precision', {})

        ## Look up table for exact dimensional labels (like integers)
        self.idx_label_lut = {}

        ## Dictionary of custom indexing handlers
        self.idx_handlers = {}

        ## Call OrderedDict __init__ to create dictionary of values
        super().__init__(**kwargs)

        ## Cast each item in the dictionary to a numpy array. If items are objects, numpy will use the object
        ## dtype for the array. Single items (not arrays) will be cast as single item arrays.
        for k,v in self.items():
            ## Cast single items as numpy arrays with np.array([v])
            self[k] = np.array(v) if isinstance(v, (list, np.ndarray, tuple)) else np.array([v])

            ## Provide default values for index precision if the values are floats
            f64 = np.dtype(np.float64)
            f32 = np.dtype(np.float32)

            if (k not in self.idx_precision) and (self[k].dtype in [f64, f32]):
                self.idx_precision[k] = self.DEFAULT_PRECISION

            ## If the labels are not floats, they are used as exact indices and we create a lookup table that
            ## maps the label to it's index in the dimension
            else:
                self.idx_label_lut[k] = {vv:i for i,vv in enumerate(self[k])}

            
    def set_precision(self, **kwargs):
        """ Sets precision for given dimensional indices. Accpets key value pairs where key is dimensional key
            and value is index precision. Precision value can be less or greater than 1, default precision is 1e-6.

            Example:
                dim = lddim(a=[1.2, 2.4, 3.1], b=[4,5,6])
                dim.set_precision(b=2, a=1e-3)
        """

        ## Update precisions only if the key already exsists in idx_precision.
        ## This ensures only floats have idx_precision specified.
        for k,v in self.idx_precision.items():
            self.idx_precision[k] = kwargs.get(k, self.idx_precision[k])

    def set_idx_handler(self, **kwargs):
        """ Sets a custom index handler for each dimension given.

            Handlers must accept two arguments, a slice with index values, and an array of index labels,
            and return a slice of standard numpy indices.

            Example:
                def ex_handler(v_slice, labels):
                    ....
                    return slice(..., ...)

                dim = lddim(a=[1.2, 2.4, 3.1], b=[4,5,6])
                dim.set_idx_handler(b=ex_handler)
        """
        for k,v in kwargs:
            if k in self.keys():
                self.idx_handlers[k] = v

    @property
    def shape(self):
        """ Returns shape of the ldarray that uses this lddim for it's dimensional indexing.
        """
        return tuple([len(v) for k,v in self.items()])


    def __str__(self):
        ## breaks out each key-value pair into it's own line for easier reading 
        s = '{\n'
        for k,v in self.items():
            s += k + ': ' + str(v) + '\n'
        return s+ '}'

    def __repr__(self):
        return self.__str__()

class ldarray(np.ndarray):
    """ Labeled numpy array. Subclass of np.ndarray where dimension labels can be used to index and slice
        array, similar to x-array. Indexing precision can be set on a per dimension basis, and custom indexing handlers 
        can be passed to the indexing routine to allow for indexing with objects, i.e. datetime objects.

        Creating Arrays
        --------------
        Created the same way as a normal np.ndarray, but with an additional key-value argument called dim. 'dim' is a dictionary
        of dimensional labels and must be of the lddim class. 

        Empty arrays can also be created by omitting the usual data argument and giving the constructor a dim kwarg. This creates
        a 0 filled array of the given dtype. dtype is optional and will be assigned by numpy according to the data type. If data 
        and dtype is not given, the dtype will default to np.float (default for np.zeros).
        Example:
            dim = lddim(a=[1,2], b=['data1', 'data2', 'data3'])
            ld_empty = ldarray(dim=dim, dtype=np.float64)

            ld = ldarray([[10, 11, 12],[13, 14, 15]], dim=dim, dtype=np.float64)

        Indexing
        --------
        Arrays can be indexed with no change to how normal numpy arrays work.
        Example:
        >>> ld[:, 2] 
        ldarray([12, 15])

        But can also be indexed with the dimension labels given by dim by indexing with a dictionary. The keys must match 
        the keys of the dim dictionary, and the labels can be given as single values, or contained within slices.
        Example:
        >>> ld[{'b':'data3'}] 
        ldarray([[12 15]])

        Index dictionaries do not need to contain labels for every dimension, dimensions not included in the dictionary
        will not be indexed (equivlent to using ':' in the standard numpy index).

        The result of an indexed ldarray is a ldarray with reduced dimension labels from the indexing opeation.
        The dimension labels can be veiwed at any time by accesing the 'dim' class member.
        Example:
        >>> ld.dim

            {
            a: [1 2]
            b: ['dat1' 'data2' 'data3']
            }

        Indexing with a dictionary can be used for setting data as well.
        Example:
        >>> ld[{'a':2}] = 7

        ldarray([[10, 11, 12],
                 [ 7,  7,  7]])

    """
    def __new__(cls, input_=None, dim=None, dtype=None):
        
        ## create 0 filled array if no data is given in the constructor
        if np.all(input_ == None):
            shape = tuple([len(v) for k,v in dim.items()])
            obj = np.zeros(shape, dtype=dtype).view(cls)

        ## cast input data to ldarray type
        else:             
            obj = np.asarray(input_).view(cls)

            ## If dim is not compatible with the data shape return a standard numpy array
            if (dim is None) or (not check_shapes(obj.shape, dim.shape)):
                raise TypeError('Axis label of shape {} is not compatible with data of shape {}.'.format(dim.shape, obj.shape))

        ## copy dim and assign as member variable
        obj.dim = dcopy(dim)
        
        return obj


    def __array_finalize__(self, obj):
        ## required method of subclasses of numpy. Sets unique member variables of new instances
        if obj is None: return
        self.dim = getattr(obj, 'dim', lddim())


    def __getitem__(self, key):

        ## if index is a dictionary, use the dimension labels to index
        if isinstance(key, dict):
            ## get standard numpy indices, will be a tuple of slices of length equal to the
            ## number of dimensions.
            idx = self._v2idx(key)

            ## index object with this __getitem__ method. Not recursive because the index value
            ## is no longer a dictionary and will execute the else clause below.
            ## Object will have a new dim member variable that matches the indexed axis
            obj = self[idx]

            return obj

        else:
            ## index is a standard index of slices or integers so pass key to the numpy indexing routine.
            ## this object will have the same dim (not copied) as the object it was indexed from since numpy uses 
            ## the __array_finalize__ method declared above to construct the new array.
            obj = super(ldarray, self).__getitem__(key)
            
            ## shape length can be greater after indexing if np.newaxis was used. In this case just
            ## return a standard numpy array and make the user responsible for adding dimensional labels.
            if len(obj.shape) > len(self.shape):
                return np.array(obj)

            ## obj could be a single value. In this case we don't have to worry about indexing the dimension labels 
            ## so just return the obj
            if not len(obj.shape):
                return obj

            ## copy dim for the new ldarray object so the following doesn't affect the original object dim
            ndim = dcopy(obj.dim)

            ## At this point, we need to index the dimension dictionary so it matches the obj data,
            ## and remove axis that were indexed out completely.

            ## Cast index key as a tuple if it's a single value
            nkey = tuple(key) if isinstance(key, (tuple, list)) else (key,)

            ## Initalize list of indices for each dimension that will be used to index the label arrays in dim. 
            ## Length is the original array shape length so it matches ndim.
            idx = [slice(None,None) for i in range(len(self.shape))]
            
            ## step through index keys and update idx with the appropriate keys.
            ## Keys are always in order of the array dimensions, but axis can be skipped with the Ellipsis operator.
            idx_i = 0 
            for ii, k in enumerate(nkey):
                ## jump the current index (idx_i) ahead if there is an Ellipsis.
                if isinstance(k, type(Ellipsis)):
                    ## key after an Ellipsis indexes the dimension starting from the end of the key list
                    idx_i = len(idx) - (len(nkey) - idx_i) 

                else:
                    ## update idx with the key, if no key is given for a axis it defaults to ':'
                    idx[idx_i] = k

                idx_i += 1

            ## use idx to index each array of dimension labels in ndim
            for i, (k,v) in enumerate(self.dim.items()):
                ## numpy removes the dimension if indexed with a integer 
                ## so remove it from the dimension label dictionary.
                if isinstance(idx[i], int):
                    ndim.pop(k)
                    ## also remove the key from the precision and handler dictionaries if it exsits.
                    ndim.idx_precision.pop(k, None)
                    ndim.idx_handlers.pop(k, None)
                else:
                    ## reduce the label array for current axis to match the indexed numpy array
                    ## idx has a value for every dimnesion so we can use i to get the correct index key
                    ndim[k] = v[idx[i]]

            ## revert to standard numpy array if we weren't able to keep dim consistent with the numpy array data
            if not check_shapes(obj.shape, ndim.shape):
                return np.array(obj)

            ## if dim and the obj shape match, update the dim member of the indexed obj and return
            obj.dim = ndim
            return obj


    def __setitem__(self, key, value):
        ## __setitem__ will not change the axis shape, so we don't need to modify the axis labels.
        
        ## if the index key is not a dictionary, use the numpy __setitem__
        if not isinstance(key, dict):
            super(ldarray, self).__setitem__(key, value)

        ## if key is dictionary, convert to standard indices with _v2idx and set value
        else:
            idx = self._v2idx(key)
            self[idx] = value
        

    def squeeze(self):
        """ Same as numpy.squeeze but also removes the axis labels
        """
        ## build full idx key of all the dimensions
        idx = [slice(None) for i in range(len(self.shape))]

        for i, s in enumerate(self.shape):
            ## if axis length is 1, replace index key with an integer index. numpy will remove 
            ## the axis and the __getitem__ routine will remove the indexed out axis label
            if s <= 1:
                idx[i] = 0

        ## call __getitem__ and return
        return self[tuple(idx)]


    def _v2idx(self, dct_idx):
        ### Converts dictionary indices to standard numpy indices. Using dictionaries as indices avoids the need
        ### to remember the dimensions order.

        ## Start with list of slices that index the full range of each dimension. The slices will be updated with the
        ## bounds given in the dictionary index
        np_index = [slice(None,None) for i in range(len(self.shape))]
        dim_keys = list(self.dim.keys())
        
        for k,v in dct_idx.items():
            ## Return a type error if the dictionary has a key that is not tracked in the dimensional dictionary.
            if k not in dim_keys:
                raise TypeError('Invalid index key: {}'.format(k))

            ## get the index of the current dimension key in the array shape. dim_keys is the keys from an
            ## Ordered Dictionary so the order will hold.
            np_i = dim_keys.index(k)

            ## get values of the dimension labels. This is a 1D numpy array where each value is unique
            d_labels = self.dim[k]

            is_idx_slice = (v.__class__ == slice)

            ## cast v as a slice if not already, this allows us to use v.start and v.stop below. Both v.start and 
            ## v.stop will be the same when a single value is cast to a slice.
            if not is_idx_slice:
                v = slice(v, v, None)
            
            ## check if this dimension has a custom handler defined
            if k in self.dim.idx_handlers.keys():
                ## get handler from dictionary
                handler = self.dim.idx_handlers[k]

                ## handler will return a slice. 
                np_index[np_i] = handler(v, d_labels)

            ## The dimensional key will be in the idx_precision dictionary if the labels are floats.
            ## Use approximate indexing based on index precision given in the lddim class.
            elif k in self.dim.idx_precision.keys():
                ## get dimension precision
                precision = self.dim.idx_precision[k]

                ## initialize slice values to None
                s_start, s_stop, s_step = None, None, v.step
                ## temporary array to store start and stop indices
                s_temp = []
                ## for both start and stop labels, find nearest index if it exists with the given precision
                for v_s in [v.start, v.stop]:
                    ## skip if the label is None
                    if v_s == None:
                        s_temp.append(None)
                        continue
                    ## subtract start value from label values
                    label_diff = np.abs(v_s - d_labels)

                    ## get minimum value and index from difference array
                    lmin = np.min(label_diff)
                    lmin_arg = np.argmin(label_diff)

                    ## raise Type error if no label exists within given precision
                    if lmin > precision:
                        raise TypeError('Index label of {} is outside precision given for dimension key {}.'.format(v.start, k))
                    ## set slice value to index of minimum value if within precision
                    s_temp.append(lmin_arg)
                
                ## unpack temporary array
                s_start, s_stop = s_temp
                ## populate numpy index with slice of standard indices
                np_index[np_i] = slice(s_start, s_stop, s_step)

            ## label index is exact (integer or string) so we use the lookup table
            else:
                ## get lookup table for current dimension
                label_lut = self.dim.idx_label_lut[k]

                ## convert labels to standard indices and build slice. Slice step is not modified, a step of 2 will still index 
                ## every other value.
                s_start = label_lut[v.start] if v.start != None else None
                s_stop = label_lut[v.stop] +1 if v.stop != None else None
                s_step = v.step

                ## populate numpy index with slice of standard indices
                np_index[np_i] = slice(s_start, s_stop, s_step)

            ## replace slices with integers if an integer index was given so that numpy will squeeze the dimension when indexed
            if not is_idx_slice:
                np_index[np_i] = int(np_index[np_i].start)

        return tuple(np_index)

    def get_axis_num(self, key):
        dim_keys = list(self.dim.keys())
        return dim_keys.index(key)

    # def save(self, file_):
    #     np.savez(file_, data=self, dim=self.dim)

    # @classmethod
    # def load(self, file_):
    #     loadf = np.load(file_.with_suffix(r'.npz'), allow_pickle=True)
    #     data = loadf['data'][()]
    #     dim = loadf['dim'][()]
    #     return ldarray(data, dim)

    def run_loop(self, func, index_to=None, dtype='float64', progress_interval=0):
        ## get rid of element_shape, need to have self be the full dimensioned value and index appropriately in the run_loop

        dim_keys = list(self.dim.keys())
        shape = self.shape[:index_to]
        func_run_idx = [np.prod(shape[i+1:]) for i in range(len(shape))]

        if func.__class__ != list:
            func_list = [None]*len(shape)
            func_list[-1] = func
            func = func_list

        vals = [None]*len(self.dim)
        stime = time.time()
        iter_ = np.prod(shape)

        for i in range(iter_):
            idx = np.unravel_index(i, shape)
            for d in range(len(shape)):
                vals[d] = self.dim[dim_keys[d]][idx[d]]
                if ((i % func_run_idx[d]) == 0) and (func[d] != None):
                    self[idx] = func[d](*vals[:d+1], idx=idx[:d+1])
            
            if progress_interval:
                if (i % progress_interval == 0):
                    sys.stdout.write('\r {:.2f}% {}\t\t\t\t'.format(((i+1)/iter_)*100, vals))
        
        if progress_interval:
            print('\nIterations: {}, Timer: {:0.4f}s'.format(self.iter, time.time()-stime))