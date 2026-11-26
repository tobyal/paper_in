"""Plot recorded optimization statistics, not segmentation accuracy."""
from common import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
data=np.genfromtxt(ROOT/'outputs/A/saga_model/training_metrics.csv',delimiter=',',names=True);fig,axes=plt.subplots(2,2,figsize=(12,7),layout='constrained');x=data['iteration']
def smooth(y,k=20):return np.convolve(y,np.ones(k)/k,mode='valid') if len(y)>=k else y
for field,title,ax in [('loss','Official SAGA training loss',axes[0,0]),('feature_norm','Rendered feature norm',axes[1,0]),('peak_allocated_bytes','Torch peak allocated memory (GiB)',axes[1,1])]:
    y=data[field]/(2**30 if field=='peak_allocated_bytes' else 1);ax.plot(x,y,alpha=.25,lw=.7);s=smooth(y);ax.plot(x[len(x)-len(s):],s,lw=1.6);ax.set_title(title);ax.set_xlabel('Iteration');ax.grid(alpha=.2)
ax=axes[0,1]
for field,label in [('positive_cosine','Same-mask pairs'),('negative_cosine','Different-mask pairs')]:
    y=smooth(data[field]);ax.plot(x[len(x)-len(y):],y,label=label)
ax.set_title('Training pair cosine similarity');ax.legend();ax.set_xlabel('Iteration');ax.grid(alpha=.2);fig.suptitle('Shared native 3DGS affinity field | optimization diagnostics, not ground-truth accuracy');fig.savefig(ROOT/'outputs/A/training_curves.png',dpi=160)
