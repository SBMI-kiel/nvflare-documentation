# Copyright (c) 2023, NVIDIA CORPORATION.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import copy
import os
import uuid
from typing import Union
from tqdm import tqdm

import numpy as np
import torch
import torch.optim as optim
from torch.utils.tensorboard import SummaryWriter
from monai.transforms import LoadImaged, EnsureChannelFirstd, ScaleIntensityd, Compose
from monai.apps import MedNISTDataset
from monai.data import DataLoader
from monai.networks.nets import densenet121

from nvflare.apis.fl_constant import FLMetaKey, ReturnCode
from nvflare.app_common.abstract.fl_model import FLModel, ParamsType
from nvflare.app_common.abstract.model_learner import ModelLearner
from nvflare.app_common.app_constant import AppConstants, ModelName, ValidateType
from nvflare.app_common.utils.fl_model_utils import FLModelUtils


class MedNISTModelLearner(ModelLearner):  
    def __init__(
        self,
        train_idx_root: str = "/code/dataset",
        aggregation_epochs: int = 1,
        lr: float = 1e-2,
        central: bool = False,
        analytic_sender_id: str = "analytic_sender",
        batch_size: int = 64,
        num_workers: int = 0,
    ):
        """

        Args:
            train_idx_root: Directory for mednist data.
            aggregation_epochs: the number of training epochs for a round. Defaults to 1.
            lr: local learning rate. Float number. Defaults to 1e-2.
            central: Bool. Whether to simulate central training. Default False.
            analytic_sender_id: id of `AnalyticsSender` if configured as a client component.
                If configured, TensorBoard events will be fired. Defaults to "analytic_sender".
            batch_size: batch size for training and validation.
            num_workers: number of workers for data loaders.

        Returns:
            an FLModel with the updated local model differences after running `train()`, the metrics after `validate()`,
            or the best local model depending on the specified task.
        """
        super().__init__()
        # trainer init happens at the very beginning, only the basic info regarding the trainer is set here
        # the actual run has not started at this point
        self.root_dir = train_idx_root
        self.aggregation_epochs = aggregation_epochs
        self.lr = lr
        self.best_acc = 0.0
        self.central = central
        self.batch_size = batch_size
        self.num_workers = num_workers
        self.analytic_sender_id = analytic_sender_id

        # Epoch counter
        self.epoch_of_start_time = 0
        self.epoch_global = 0

        # following will be created in initialize() or later
        self.local_model_file = None
        self.best_local_model_file = None
        self.writer = None
        self.device = None
        self.model = None
        self.optimizer = None
        self.criterion = None
        self.transform_train = None
        self.transform_valid = None
        self.train_dataset = None
        self.valid_dataset = None
        self.train_loader = None
        self.valid_loader = None

    def initialize(self):
        """
        Note: this code assumes a FL simulation setting
        Datasets will be initialized in train() and validate() when calling self._create_datasets()
        as we need to make sure that the server has already downloaded and split the data.
        """

        # when the run starts, this is where the actual settings get initialized for trainer
        self.info(
            f"Client {self.site_name} initialized at \n {self.app_root} \n with args: {self.args}",
        )

        self.local_model_file = os.path.join(self.app_root, "local_model.pt")
        self.best_local_model_file = os.path.join(self.app_root, "best_local_model.pt")

        # Select local TensorBoard writer or event-based writer for streaming
        self.writer = self.get_component(
            self.analytic_sender_id
        )  # user configured config_fed_client.json for streaming
        if not self.writer:  # use local TensorBoard writer only
            self.writer = SummaryWriter(self.app_root)

        self.initialize_common()

    def initialize_local(self):
        self.app_root = "local_runs/" + str(uuid.uuid4())

        self.initialize()

    def initialize_common(self):


        # set the training-related parameters
        # can be replaced by a config-style block
        self.device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        self.model = densenet121(spatial_dims=2, in_channels=1, out_channels=6).to(self.device)
        self.optimizer = optim.SGD(self.model.parameters(), lr=self.lr, momentum=0.9)
        self.criterion = torch.nn.CrossEntropyLoss()
        self.transform_train = self.transform_valid= Compose(
            [
            LoadImaged(keys="image", image_only=True),
            EnsureChannelFirstd(keys="image"),
            ScaleIntensityd(keys="image"),
        ]
        )
        self._create_datasets()

    def _create_datasets(self):

        if self.train_dataset is None or self.train_loader is None:

            self.train_dataset = MedNISTDataset(
                root_dir=self.root_dir,
                section="training",
                download=True,
                transform=self.transform_train,
            )
            self.train_loader = DataLoader(
                self.train_dataset, batch_size=self.batch_size, shuffle=True, num_workers=self.num_workers
            )

        if self.valid_dataset is None or self.valid_loader is None:
            self.valid_dataset = MedNISTDataset(
                root_dir=self.root_dir,
                section="validation",
                download=False,
                transform=self.transform_valid,
            )
            self.valid_loader = DataLoader(
                self.valid_dataset, batch_size=self.batch_size, shuffle=False, num_workers=self.num_workers
            )

    def finalize(self):
        # collect threads, close files here
        pass

    def local_train(self, train_loader, val_freq: int = 0):
        for epoch in range(self.aggregation_epochs):
            self.model.train()
            epoch_len = len(train_loader)
            self.epoch_global = self.epoch_of_start_time + epoch
            self.info(f"Local epoch {self.site_name}: {epoch + 1}/{self.aggregation_epochs} (lr={self.lr})")
            avg_loss = 0.0
            for i, train_data in enumerate(tqdm(train_loader)):
                inputs, labels = train_data["image"].to(self.device), train_data["label"].to(self.device)
                # zero the parameter gradients
                self.optimizer.zero_grad()
                # forward + backward + optimize
                outputs = self.model(inputs)
                loss = self.criterion(outputs, labels)

                loss.backward()
                self.optimizer.step()
                current_step = epoch_len * self.epoch_global + i
                avg_loss += loss.item()
            print("Train loss", avg_loss / len(train_loader))
            self.writer.add_scalar("train_loss", avg_loss / len(train_loader), current_step)
            if val_freq > 0 and epoch % val_freq == 0:
                acc = self.local_valid(self.valid_loader, tb_id="val_acc_local_model")
                if acc > self.best_acc:
                    self.best_acc = acc
                    self.save_model(is_best=True)

    def save_model(self, is_best=False):
        # save model
        model_weights = self.model.state_dict()
        save_dict = {"model_weights": model_weights, "epoch": self.epoch_global}
        if is_best:
            save_dict.update({"best_acc": self.best_acc})
            torch.save(save_dict, self.best_local_model_file)
        else:
            torch.save(save_dict, self.local_model_file)

    def train(self, model: FLModel) -> Union[str, FLModel]:
        self._create_datasets()

        # get round information
        self.info(f"Current/Total Round: {self.current_round + 1}/{self.total_rounds}")
        self.info(f"Client identity: {self.site_name}")

        # update local model weights with received weights
        global_weights = model.params

        # Before loading weights, tensors might need to be reshaped to support HE for secure aggregation.
        local_var_dict = self.model.state_dict()
        model_keys = global_weights.keys()
        for var_name in local_var_dict:
            if var_name in model_keys:
                weights = global_weights[var_name]
                try:
                    # reshape global weights to compute difference later on
                    global_weights[var_name] = np.reshape(weights, local_var_dict[var_name].shape)
                    # update the local dict
                    local_var_dict[var_name] = torch.as_tensor(global_weights[var_name])
                except BaseException as e:
                    raise ValueError(f"Convert weight from {var_name} failed") from e
        self.model.load_state_dict(local_var_dict)

        # local steps
        epoch_len = len(self.train_loader)
        self.info(f"Local steps per epoch: {epoch_len}")

        # make a copy of model_global as reference for potential FedProx loss or SCAFFOLD
        model_global = copy.deepcopy(self.model)
        for param in model_global.parameters():
            param.requires_grad = False

        # local train
        self.local_train(
            train_loader=self.train_loader,
            val_freq=1 if self.central else 0,
        )
        self.epoch_of_start_time += self.aggregation_epochs

        # perform valid after local train
        acc = self.local_valid(self.valid_loader, tb_id="val_acc_local_model")
        self.info(f"val_acc_local_model: {acc:.4f}")

        # save model
        self.save_model(is_best=False)
        if acc > self.best_acc:
            self.best_acc = acc
            self.save_model(is_best=True)

        # compute delta model, global model has the primary key set
        local_weights = self.model.state_dict()
        model_diff = {}
        for name in global_weights:
            if name not in local_weights:
                continue
            model_diff[name] = np.subtract(local_weights[name].cpu().numpy(), global_weights[name], dtype=np.float32)
            if np.any(np.isnan(model_diff[name])):
                self.stop_task(f"{name} weights became NaN...")
                return ReturnCode.EXECUTION_EXCEPTION

        # return an FLModel containing the model differences
        fl_model = FLModel(params_type=ParamsType.DIFF, params=model_diff)

        FLModelUtils.set_meta_prop(fl_model, FLMetaKey.NUM_STEPS_CURRENT_ROUND, epoch_len)
        self.info("Local epochs finished. Returning FLModel")
        return fl_model

    def get_model(self, model_name: str) -> Union[str, FLModel]:
        # Retrieve the best local model saved during training.
        if model_name == ModelName.BEST_MODEL:
            try:
                # load model to cpu as server might or might not have a GPU
                model_data = torch.load(self.best_local_model_file, map_location="cpu")
            except Exception as e:
                raise ValueError("Unable to load best model") from e

            # Create FLModel from model data.
            if model_data:
                # convert weights to numpy to support FOBS
                model_weights = model_data["model_weights"]
                for k, v in model_weights.items():
                    model_weights[k] = v.numpy()
                return FLModel(params_type=ParamsType.FULL, params=model_weights)
            else:
                # Set return code.
                self.error(f"best local model not found at {self.best_local_model_file}.")
                return ReturnCode.EXECUTION_RESULT_ERROR
        else:
            raise ValueError(f"Unknown model_type: {model_name}")  # Raised errors are caught in LearnerExecutor class.

    def local_valid(self, valid_loader, tb_id=None):
        self.model.eval()
        with torch.no_grad():
            correct, total = 0, 0
            for val_data in tqdm(valid_loader):
                inputs, labels = val_data["image"].to(self.device), val_data["label"]
                outputs = self.model(inputs).detach().to("cpu")
                _, pred_label = torch.max(outputs.data, 1)

                total += inputs.data.size()[0]
                correct += (pred_label == labels.data).sum().item()
            metric = correct / float(total)
            if tb_id:
                self.writer.add_scalar(tb_id, metric, self.epoch_global)
        return metric

    def validate(self, model: FLModel) -> Union[str, FLModel]:
        self._create_datasets()

        # get validation information
        self.info(f"Client identity: {self.site_name}")

        # update local model weights with received weights
        global_weights = model.params

        # Before loading weights, tensors might need to be reshaped to support HE for secure aggregation.
        local_var_dict = self.model.state_dict()
        model_keys = global_weights.keys()
        n_loaded = 0
        for var_name in local_var_dict:
            if var_name in model_keys:
                weights = torch.as_tensor(global_weights[var_name], device=self.device)
                try:
                    # update the local dict
                    local_var_dict[var_name] = torch.as_tensor(torch.reshape(weights, local_var_dict[var_name].shape))
                    n_loaded += 1
                except BaseException as e:
                    raise ValueError(f"Convert weight from {var_name} failed") from e
        self.model.load_state_dict(local_var_dict)
        if n_loaded == 0:
            raise ValueError(f"No weights loaded for validation! Received weight dict is {global_weights}")

        # get validation meta info
        validate_type = FLModelUtils.get_meta_prop(
            model, FLMetaKey.VALIDATE_TYPE, ValidateType.MODEL_VALIDATE
        )  # TODO: enable model.get_meta_prop(...)
        model_owner = self.get_shareable_header(AppConstants.MODEL_OWNER)

        # perform valid
        train_acc = self.local_valid(
            self.train_loader,
            tb_id="train_acc_global_model" if validate_type == ValidateType.BEFORE_TRAIN_VALIDATE else None,
        )
        self.info(f"training acc ({model_owner}): {train_acc:.4f}")

        val_acc = self.local_valid(
            self.valid_loader,
            tb_id="val_acc_global_model" if validate_type == ValidateType.BEFORE_TRAIN_VALIDATE else None,
        )
        self.info(f"validation acc ({model_owner}): {val_acc:.4f}")
        self.info("Evaluation finished. Returning result")

        if val_acc > self.best_acc:
            self.best_acc = val_acc
            self.save_model(is_best=True)

        val_results = {"train_accuracy": train_acc, "val_accuracy": val_acc}
        return FLModel(metrics=val_results)


if __name__ == "__main__":
    learner = MedNISTModelLearner()
    learner.initialize_local()
    learner.local_train(learner.train_loader)
    learner.local_valid(learner.valid_loader)

